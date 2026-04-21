"""
ASP-FEAT-ASP-04 v1.0 §6.1 — POST /api/v1/ai/documents upload endpoint
(I-DOC-05).

Multipart PDF upload, tenant-scoped MinIO storage, documents-registry
INSERT, ADR-006 cost-emission resilience, structlog transitions.

Auth: `X-ASP-API-Key` via the Gateway's `verify_api_key` dependency.
Tenant identity is the authenticated tenant — never read from form
parts (§7.1).

Errors follow RFC 7807 envelope per ASP-FEAT-ASP-00 v1.0.

ASP-FEAT-ASP-04 v1.0 §6.1 governs the 10 MB upload cap via
`settings.ASP_DOC_UPLOAD_MAX_MB` (OQ-2 ruling: 10 MB, corrects the
§6.1 Batch 2 text which had 20 MB as a placeholder).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.gateway.auth import verify_api_key
from app.infra import storage
from app.schemas.doc_intelligence_schemas import DocumentUploadResponse


log = structlog.get_logger()

router = APIRouter()


_ACCEPTED_CONTENT_TYPES = {"application/pdf"}
_ACCEPTED_TYPE_HINTS = {"invoice", "receipt", "contract", "other"}
_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._\- ]")


def _sanitise_filename(raw: Optional[str]) -> str:
    """Strip path separators, enforce UTF-8, truncate to 255 chars.

    Filenames with zero sanitisable characters fall back to
    'upload.pdf' — the storage key uses the server-generated UUID,
    so the filename is purely display metadata.
    """
    if not raw:
        return "upload.pdf"
    # Reject non-UTF-8 by round-tripping
    try:
        raw = raw.encode("utf-8").decode("utf-8")
    except UnicodeError:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/validation",
                "title": "Invalid filename encoding",
                "detail": "filename must be valid UTF-8",
            },
        )
    # Strip path separators + disallow .. sequences
    cleaned = raw.replace("\\", "").replace("/", "").replace("..", "")
    # Additional defensive whitelist (keep only alphanumerics, dots,
    # dashes, underscores, spaces; strip everything else)
    cleaned = _SAFE_FILENAME_CHARS.sub("", cleaned).strip()
    if not cleaned:
        cleaned = "upload.pdf"
    # Truncate to DB column width
    return cleaned[:255]


@router.post(
    "/ai/documents",
    status_code=201,
    response_model=DocumentUploadResponse,
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type_hint: Optional[str] = Form(default=None),
    tenant=Depends(verify_api_key),
) -> DocumentUploadResponse:
    """Upload a PDF for ASP-04 Doc Intelligence processing."""

    # --- Content-type whitelist (AC-DOC-S3-02) ---------------------------

    if file.content_type not in _ACCEPTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "type": "/errors/unsupported-media-type",
                "title": "Unsupported media type",
                "detail": (
                    f"file Content-Type must be application/pdf; "
                    f"got {file.content_type!r}"
                ),
            },
        )

    # --- document_type_hint whitelist ------------------------------------

    if document_type_hint is not None and document_type_hint not in _ACCEPTED_TYPE_HINTS:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "/errors/validation",
                "title": "Invalid document_type_hint",
                "detail": (
                    f"document_type_hint must be one of "
                    f"{sorted(_ACCEPTED_TYPE_HINTS)}; got {document_type_hint!r}"
                ),
            },
        )

    # --- Size check before reading bytes (AC-DOC-S3-03) ------------------
    #
    # FastAPI's UploadFile has `.size` since 0.111. If unset (older
    # clients streaming unknown-length bodies), fall back to a
    # post-read length check after spool.

    max_bytes = settings.ASP_DOC_UPLOAD_MAX_MB * 1024 * 1024
    declared_size = getattr(file, "size", None)
    if declared_size is not None and declared_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "type": "/errors/payload-too-large",
                "title": "Payload too large",
                "detail": (
                    f"file size {declared_size} bytes exceeds max "
                    f"{settings.ASP_DOC_UPLOAD_MAX_MB} MB"
                ),
            },
        )

    # Read bytes (FastAPI's UploadFile spools to disk for large bodies)
    file_bytes = await file.read()
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "type": "/errors/payload-too-large",
                "title": "Payload too large",
                "detail": (
                    f"file size {len(file_bytes)} bytes exceeds max "
                    f"{settings.ASP_DOC_UPLOAD_MAX_MB} MB"
                ),
            },
        )

    # --- Secondary MIME sniff (defensive) --------------------------------
    # %PDF magic bytes. Reject mismatches — Content-Type could be
    # spoofed by a client.
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=415,
            detail={
                "type": "/errors/unsupported-media-type",
                "title": "File content is not a PDF",
                "detail": "file content does not start with PDF magic bytes",
            },
        )

    # --- Server-side identity + storage path (ADR-013 tenant prefix) ----

    document_id = str(uuid.uuid4())
    original_filename = _sanitise_filename(file.filename)
    storage_path = f"{tenant.id}/{document_id}.pdf"

    # --- MinIO write (bytes never transit any other component) ----------

    try:
        storage.upload(storage_path, file_bytes, content_type="application/pdf")
    except Exception as e:
        log.error(
            "asp_doc_upload_storage_failure",
            tenant_id=str(tenant.id),
            error=str(e),
            reason="storage_write",
        )
        raise HTTPException(
            status_code=500,
            detail={
                "type": "/errors/internal",
                "title": "Internal error",
                "detail": "storage write failed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # --- documents registry INSERT via per-invocation async engine ------
    #
    # Same loop-affinity discipline as the DEFECT-024 fix: fresh engine
    # scoped to this request, disposed before return. The request
    # already has its own event loop (FastAPI lifecycle); this engine
    # lives only for the duration of the INSERT.

    uploaded_at = datetime.now(timezone.utc)
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO documents
                      (id, tenant_id, original_filename, storage_path,
                       document_type, classification_confidence,
                       extraction_status, extraction_job_id,
                       extracted_fields, uploaded_at, updated_at)
                    VALUES
                      (:id, :tenant_id, :original_filename, :storage_path,
                       :document_type, NULL,
                       'pending', NULL,
                       NULL, :uploaded_at, :uploaded_at)
                """),
                {
                    "id": document_id,
                    "tenant_id": str(tenant.id),
                    "original_filename": original_filename,
                    "storage_path": storage_path,
                    # document_type_hint is advisory for the classify
                    # step — stored here for audit, not
                    # authoritatively as the final document_type
                    # (which the classifier populates).
                    "document_type": document_type_hint,
                    "uploaded_at": uploaded_at,
                },
            )
    except Exception as e:
        log.error(
            "asp_doc_upload_db_failure",
            tenant_id=str(tenant.id),
            document_id_pending=document_id,
            storage_path=storage_path,
            error=str(e),
        )
        # NOTE: bytes are in MinIO but no registry row exists. This
        # is an orphan-blob case flagged in §6.6 — ops-responsibility
        # cleanup in v1.0; v1.1 may add a reaper task.
        raise HTTPException(
            status_code=500,
            detail={
                "type": "/errors/internal",
                "title": "Internal error",
                "detail": "document registry write failed",
                "request_id": getattr(request.state, "request_id", None),
            },
        )
    finally:
        await engine.dispose()

    # --- ADR-006 cost emission (wrapped; upload has zero LLM cost) ------

    try:
        from app.cost.meter import emit_cost_event
        await emit_cost_event(
            request_id=str(uuid.uuid4()),  # upload has no caller request_id chain
            tenant_id=str(tenant.id),
            caller_module=request.headers.get("x-asp-caller-module", "unknown"),
            service_type="doc_intelligence",
            task="upload",
            model="n/a",
            quality_tier="standard",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_ms=0,
        )
    except Exception as cost_exc:
        # ADR-006: cost-meter exception must NOT break the response.
        log.warning(
            "asp_doc_upload_cost_emission_failed",
            tenant_id=str(tenant.id),
            document_id=document_id,
            error=str(cost_exc),
        )

    # --- Success structlog + response -----------------------------------

    log.info(
        "asp_doc_upload_succeeded",
        tenant_id=str(tenant.id),
        document_id=document_id,
        storage_path=storage_path,
        original_filename=original_filename,
        size_bytes=len(file_bytes),
    )

    return DocumentUploadResponse(
        document_id=document_id,
        storage_path=storage_path,
        tenant_id=str(tenant.id),
        original_filename=original_filename,
        uploaded_at=uploaded_at.isoformat().replace("+00:00", "Z"),
    )
