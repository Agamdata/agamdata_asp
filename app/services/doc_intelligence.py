"""
ASP-04 Doc Intelligence Service (Async)

Supported tasks:
- extract_document
- classify_document

Async flow: Gateway creates job record and dispatches Celery task
immediately. The Celery worker processes the job, then fires the
webhook.

**ASP-DEFECT-024 fix (2026-04-21, ASP-FEAT-ASP-04 v1.0 S-1, I-DOC-01).**
Previous implementation used synchronous `sqlalchemy.create_engine`
with psycopg2 driver derived from `settings.DATABASE_URL` by
regex-stripping `+asyncpg`. psycopg2 was NOT in `requirements.txt`
— the Docker image has only asyncpg. Every ASP-04 Celery task that
attempted a DB write would `ModuleNotFoundError: No module named
'psycopg2'` on first execution. The bug was latent in pilot because
no consumer had driven the ASP-04 Celery worker end-to-end — the
enqueue path (async session → async_jobs INSERT) worked, but the
worker path had never completed.

**I-DOC-01 fix.** All three DB-touching sites ported to async via
`create_async_engine` + `engine.dispose()` per DEFECT-022 playbook
(reference implementation: `app/cost/aggregator.py`). The Celery task
wraps each async helper in its own `asyncio.run(_helper(...))` call.
Per-invocation engine — no pool reuse across `asyncio.run()`
boundaries (loop-affinity rule, `ENGINEERING-PLAYBOOK.md` §12).

**I-DOC-08 fix (bundled).** Cost emission wrapped in `try/except` per
ADR-006. Emission failure does not break the response path.

**I-DOC-09 fix (bundled).** Structlog transitions
`asp_doc_job_running` / `_completed` / `_failed` emitted at each
worker state per ADR-010 (§7.6 of the spec draft).
"""
import asyncio
import io
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.request import InvokeRequest
from app.models.response import JobAcceptedResponse
from app.infra.db import get_session
from app.models.db_models import AsyncJob
# I-DOC-04 — output schemas migrated to a dedicated module. Import
# for backwards-compatible handler dispatch; no behavioural change.
from app.schemas.doc_intelligence_schemas import (
    ExtractDocumentOutput,
    ClassifyDocumentOutput,
    ExtractInvoiceOutput,  # I-DOC-07 wires this in the extract path
    LineItem,
)

log = structlog.get_logger()

# I-DOC-07 (ASP-FEAT-ASP-04 v1.0 §11) — extract_invoice joins the
# task set. VALID_TASKS is the single source of truth aggregated into
# SERVICE_CAPABILITIES ("doc_intelligence") at capabilities-router
# import time (app/api/capabilities.py).
VALID_TASKS = {"extract_document", "classify_document", "extract_invoice"}


TASK_OUTPUT_SCHEMAS = {
    "extract_document": ExtractDocumentOutput,
    "classify_document": ClassifyDocumentOutput,
    "extract_invoice": ExtractInvoiceOutput,   # I-DOC-07
}


# ──────────────────────────────────────────────────────────────────────
# Per-task max_tokens budget (ASP-FEAT-ASP-04 v1.0 §9.6).
# extract_invoice needs 4096 for multi-line-item invoices per OQ-3
# ruling (ASP-OUT-054 Q-3 governed).
# ──────────────────────────────────────────────────────────────────────

TASK_MAX_TOKENS = {
    "classify_document": 256,
    "extract_document": 2048,
    "extract_invoice":  4096,
}


async def handle(req: InvokeRequest, model: str, request_id: str) -> JobAcceptedResponse:
    if req.task not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown doc_intelligence task: {req.task}")

    file_key = req.payload.get("file_key")
    if not file_key:
        raise HTTPException(status_code=400, detail="payload.file_key is required for doc_intelligence")

    # Security: enforce tenant prefix. Per ASP-FEAT-ASP-04 v1.0 §10.0
    # the correct status is 403 (not 404) because the file_key
    # structure discloses resource existence; this is the sole
    # documented exception to the ASP-wide cross-tenant 404 policy.
    expected_prefix = f"{req.tenant_id}/"
    if not file_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=403,
            detail={
                "type": "/errors/forbidden",
                "title": "Tenant-prefix mismatch on file_key",
                "detail": f"file_key must start with {expected_prefix}",
                "request_id": request_id,
            },
        )

    # Create job record
    job_id = str(uuid.uuid4())
    async with get_session() as session:
        job = AsyncJob(
            job_id=job_id,
            tenant_id=uuid.UUID(req.tenant_id),
            caller_module=req.caller_module,
            service_type="doc_intelligence",
            task=req.task,
            status="queued",
            webhook_url=req.payload.get("webhook_url"),
        )
        session.add(job)
        await session.commit()

    # Dispatch Celery task
    from app.worker import celery_app
    celery_app.send_task(
        "asp.doc_intelligence",
        args=[job_id, req.model_dump(), model],
    )

    log.info("doc_intelligence_queued", request_id=request_id, job_id=job_id,
             tenant_id=req.tenant_id, task=req.task)

    return JobAcceptedResponse(
        request_id=request_id,
        job_id=job_id,
        status="queued",
        message="Job accepted. Poll GET /api/v1/ai/jobs/{job_id} or await webhook.",
    )


# --- Celery task ---

def _get_celery_app():
    from app.worker import celery_app
    return celery_app


def _extract_text(file_bytes: bytes, filename: str = "") -> tuple[str, int]:
    """Extract text from PDF or DOCX. Returns (text, page_count).

    DOCX path unchanged. PDF path delegates to `_ocr_pdf` which
    implements the ASP-FEAT-ASP-04 v1.0 §9.4 governed OCR pipeline
    (pdftotext → pytesseract fallback). Non-PDF non-DOCX inputs are
    decoded as UTF-8 with replacement.
    """
    if filename.lower().endswith(".docx") or file_bytes[:4] == b"PK\x03\x04":
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
            return text, 1
        except Exception:
            pass

    if file_bytes[:4] == b"%PDF":
        return _ocr_pdf(file_bytes)

    # Plain-text fallback
    try:
        return file_bytes.decode("utf-8", errors="replace"), 1
    except Exception as e:
        log.warning("text_extraction_failed", error=str(e))
        return "", 1


def _ocr_pdf(file_bytes: bytes) -> tuple[str, int]:
    """OCR pipeline per ASP-FEAT-ASP-04 v1.0 §9.4 (I-DOC-07).

    1. Try pdfminer.six extract_text (covers text-based PDFs;
       equivalent semantic layer to pdftotext, in-process, no
       subprocess overhead).
    2. If result is empty or near-empty, fall back to pytesseract
       (scanned-image PDFs — rasterise via pdf2image, OCR each page).
    3. Return (text, page_count). Empty-OCR is the caller's
       responsibility to handle as a failed job per §8.4.
    4. 50K char tail-truncation happens in the worker AFTER this
       call — keeps this function's contract simple.
    """
    text = ""
    page_count = 1

    # Stage 1: pdfminer.six (pdftotext-equivalent; no subprocess)
    try:
        from pdfminer.high_level import extract_text as pdf_extract_text
        text = pdf_extract_text(io.BytesIO(file_bytes)) or ""
        # Estimate pages by form feed characters (pdfminer inserts \x0c
        # between pages).
        page_count = max(1, text.count("\x0c") + 1)
    except Exception as e:
        log.warning("asp_doc_ocr_pdfminer_failed", error=str(e))
        text = ""

    # Stage 2: pytesseract fallback if stage 1 returned near-empty
    # (less than 30 non-whitespace chars → likely a scanned image).
    if len(text.strip()) < 30:
        try:
            import pytesseract
            from pdf2image import convert_from_bytes
            pages = convert_from_bytes(file_bytes, dpi=200)
            page_count = max(page_count, len(pages))
            ocr_chunks = []
            for idx, page_img in enumerate(pages):
                try:
                    ocr_chunks.append(pytesseract.image_to_string(page_img))
                except Exception as pe:
                    log.warning(
                        "asp_doc_ocr_pytesseract_page_failed",
                        page_index=idx, error=str(pe),
                    )
            fallback_text = "\n\x0c".join(ocr_chunks)
            if len(fallback_text.strip()) > len(text.strip()):
                log.info(
                    "asp_doc_ocr_fallback_applied",
                    primary_chars=len(text.strip()),
                    fallback_chars=len(fallback_text.strip()),
                )
                text = fallback_text
        except ImportError as ie:
            # pytesseract / pdf2image not installed; primary path
            # result (possibly empty) returned as-is. Ops should see
            # the pdfminer_failed warn above.
            log.warning(
                "asp_doc_ocr_fallback_unavailable", error=str(ie),
            )
        except Exception as e:
            log.warning("asp_doc_ocr_pytesseract_failed", error=str(e))

    return text, page_count


def _truncate_tail(text: str, max_chars: int = 50_000) -> str:
    """§9.4 tail-truncation — keep the tail because invoice totals
    are usually at the end. Returns the last `max_chars` characters
    if `len(text) > max_chars`, else the original text.
    """
    if len(text) <= max_chars:
        return text
    log.warning(
        "asp_doc_ocr_truncated",
        original_length=len(text),
        kept_length=max_chars,
        mode="tail",
    )
    return text[-max_chars:]


# ──────────────────────────────────────────────────────────────────────
# I-DOC-06 — documents-registry async helpers
# ──────────────────────────────────────────────────────────────────────

_FILE_KEY_RE = re.compile(
    r"^(?P<tenant_id>[^/]+)/(?P<document_id>[^/]+)\.pdf$"
)


def _document_id_from_file_key(file_key: str) -> Optional[str]:
    """Parse `{tenant_id}/{document_id}.pdf` → document_id UUID str.
    Returns None if the format doesn't match — legacy direct-file-key
    path (DEPRECATED §8.3) may not follow the UUID-suffix convention."""
    m = _FILE_KEY_RE.match(file_key)
    return m.group("document_id") if m else None


async def _async_resolve_asyncjob_id(job_id_str: str) -> Optional[str]:
    """Return the UUID `async_jobs.id` for a given VARCHAR `job_id`
    string. documents.extraction_job_id FK targets the UUID PK, not
    the string identifier."""
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT id FROM async_jobs WHERE job_id = :j"),
                    {"j": job_id_str},
                )
            ).mappings().one_or_none()
    finally:
        await engine.dispose()
    return str(row["id"]) if row else None


async def _async_update_document_classify(
    document_id: str,
    document_type: Optional[str],
    confidence: Optional[float],
    extraction_job_uuid: Optional[str],
) -> None:
    """I-DOC-06 — update documents row on classify completion.

    Sets document_type + classification_confidence; links
    extraction_job_id to the async_jobs.id UUID; transitions status
    'pending' / 'classifying' → 'classifying' (left in-flight per
    the demo flow — extract_invoice moves it to 'extracting' →
    'complete'). No status override if the row is already at a
    terminal state ('complete' / 'failed').
    """
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE documents
                    SET document_type             = :document_type,
                        classification_confidence = :confidence,
                        extraction_job_id         = :job_uuid,
                        extraction_status         = CASE
                            WHEN extraction_status IN ('complete','failed')
                                 THEN extraction_status
                            ELSE 'classifying'
                        END,
                        updated_at                = NOW()
                    WHERE id = :document_id
                """),
                {
                    "document_id": document_id,
                    "document_type": document_type,
                    "confidence": confidence,
                    "job_uuid": extraction_job_uuid,
                },
            )
    finally:
        await engine.dispose()


async def _async_update_document_extract_start(
    document_id: str,
    extraction_job_uuid: Optional[str],
) -> None:
    """I-DOC-07 — transition documents row to 'extracting' at the start
    of an extract_invoice job. Links extraction_job_id if provided."""
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE documents
                    SET extraction_status = 'extracting',
                        extraction_job_id = COALESCE(:job_uuid, extraction_job_id),
                        updated_at        = NOW()
                    WHERE id = :document_id
                      AND extraction_status NOT IN ('complete','failed')
                """),
                {"document_id": document_id, "job_uuid": extraction_job_uuid},
            )
    finally:
        await engine.dispose()


async def _async_update_document_extract_complete(
    document_id: str,
    extracted_fields: dict,
) -> None:
    """I-DOC-07 — transition documents row to 'complete' with the
    extracted_fields JSONB populated. Terminal state."""
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE documents
                    SET extraction_status = 'complete',
                        extracted_fields  = CAST(:fields AS JSONB),
                        updated_at        = NOW()
                    WHERE id = :document_id
                """),
                {
                    "document_id": document_id,
                    "fields": json.dumps(extracted_fields),
                },
            )
    finally:
        await engine.dispose()


async def _async_update_document_failed(
    document_id: str,
) -> None:
    """Transition documents row to 'failed' on worker exception. No
    error text persisted to documents.extracted_fields — async_jobs
    carries error_message for audit."""
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    UPDATE documents
                    SET extraction_status = 'failed',
                        updated_at        = NOW()
                    WHERE id = :document_id
                """),
                {"document_id": document_id},
            )
    finally:
        await engine.dispose()


# ──────────────────────────────────────────────────────────────────────
# I-DOC-01 — ASYNC DB HELPERS (asyncpg, per-invocation engine)
# ──────────────────────────────────────────────────────────────────────
#
# Each of the three helpers below creates a fresh async engine scoped
# to its call and disposes it before returning. This is the governed
# pattern per ENGINEERING-PLAYBOOK.md §12 (loop-affinity rule):
# asyncpg connections carry event-loop affinity, so a pool created
# against loop A and reused from loop B will raise "got Future
# attached to a different loop". Celery tasks wrap each helper in its
# own `asyncio.run()` which creates a new event loop per invocation —
# so no pool can be shared across invocations.
#
# Per-call connection overhead is acceptable because:
#   - ASP-04 tasks fire at most a few per minute in pilot
#   - The engine is only used for one or two round-trips per call
#   - Correctness trumps microsecond-level latency here


async def _async_update_job_status(
    job_id: str,
    status: str,
    result: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    """Update `async_jobs` row for this job. Sets `completed_at` when
    status transitions to `completed` or `failed`.

    Implementation note: the terminal-state guard is computed in
    Python rather than via SQL `CASE` so the SQL statement uses each
    bind parameter in exactly one positional context. asyncpg
    strictly infers parameter types positionally and rejects
    inconsistent-type deductions when the same placeholder is used
    in both a VARCHAR-column assignment and a string-literal
    comparison (raises `AmbiguousParameterError`). See
    https://sqlalche.me/e/20/f405.
    """
    from app.config import settings

    terminal = status in ("completed", "failed")
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            if terminal:
                await conn.execute(
                    text("""
                        UPDATE async_jobs
                        SET status         = :status,
                            result_json    = :result,
                            error_message  = :error,
                            completed_at   = NOW()
                        WHERE job_id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "status": status,
                        "result": json.dumps(result) if result else None,
                        "error": error,
                    },
                )
            else:
                # Non-terminal transition (e.g. 'running') — leave
                # completed_at as whatever it was (NULL for queued→
                # running; unchanged for any re-transition).
                await conn.execute(
                    text("""
                        UPDATE async_jobs
                        SET status         = :status,
                            result_json    = :result,
                            error_message  = :error
                        WHERE job_id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "status": status,
                        "result": json.dumps(result) if result else None,
                        "error": error,
                    },
                )
    finally:
        await engine.dispose()


async def _async_emit_cost(job_id: str, usage, model: str, req_dict: dict) -> None:
    """Emit a cost_events row for this LLM call.

    Wrapped in try/except at the Celery-task boundary per ADR-006 (I-DOC-08
    bundled) — any failure here MUST NOT break the response path.

    Implementation note (I-DOC-11 regression lock): writes via a
    per-invocation `create_async_engine()` + direct INSERT rather than
    the app-wide `app.cost.meter.emit_cost_event` helper. The helper
    uses `app.infra.db.get_session()` whose pool is bound to the event
    loop that first touched it — fine for the FastAPI lifespan, fatal
    for Celery tasks that call `asyncio.run()` which creates a new loop
    per invocation. This is the same loop-affinity discipline as the
    other `_async_*` helpers here; keeping all DB writes off the
    shared pool removes the class of bug at the source. Direct SQL
    avoids the ORM bind-parameter positional-coercion pitfall
    documented in `_async_update_job_status`.
    """
    from app.config import settings
    from app.cost.meter import calculate_cost

    cost_usd = calculate_cost(model, usage.input_tokens, usage.output_tokens)

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO cost_events
                      (request_id, tenant_id, caller_module, caller_feature,
                       service_type, task, model, quality_tier,
                       input_tokens, output_tokens, cost_usd,
                       latency_ms, status, error_message, created_at)
                    VALUES
                      (:req, :tenant, :caller, :cfeat,
                       'doc_intelligence', :task, :model, :tier,
                       :inp, :out, :cost,
                       :lat, 'success', NULL, NOW())
                """),
                {
                    # The cost_events.request_id column is UUID. Cast
                    # upfront — Celery task job_id is already a UUID
                    # string so this is a no-op but makes the cast
                    # explicit.
                    "req": uuid.UUID(job_id) if isinstance(job_id, str) else job_id,
                    "tenant": uuid.UUID(req_dict["tenant_id"])
                              if isinstance(req_dict["tenant_id"], str)
                              else req_dict["tenant_id"],
                    "caller": req_dict["caller_module"],
                    "cfeat":  req_dict.get("caller_feature"),
                    "task":   req_dict["task"],
                    "model":  model,
                    "tier":   req_dict.get("quality_tier", "standard"),
                    "inp":    usage.input_tokens,
                    "out":    usage.output_tokens,
                    "cost":   cost_usd,
                    "lat":    0,
                },
            )
    finally:
        await engine.dispose()


async def _async_fetch_prompt(task: str, caller_module: str) -> Optional[dict]:
    """Fetch the prompt_templates row for this task + caller. Returns
    {system_prompt, user_prompt_template} or None if no row matches.

    Caller-module resolution order (matches the registry's level-1 +
    level-3 positions): exact caller first, then `'*'` catch-all.
    Maturity is not filtered here — the doc_intelligence handler has
    historically ignored maturity per the pre-governance contract.
    """
    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("""
                        SELECT system_prompt, user_prompt_template
                        FROM prompt_templates
                        WHERE service_type = 'doc_intelligence'
                          AND task = :task
                          AND caller_module IN (:module, '*')
                          AND is_active = TRUE
                        ORDER BY CASE WHEN caller_module = :module THEN 0 ELSE 1 END
                        LIMIT 1
                    """),
                    {"task": task, "module": caller_module},
                )
            ).mappings().one_or_none()
    finally:
        await engine.dispose()

    if row is None:
        return None
    return {
        "system_prompt": row["system_prompt"],
        "user_prompt_template": row["user_prompt_template"],
    }


def register_task(celery_app):
    @celery_app.task(name="asp.doc_intelligence", bind=True, max_retries=3)
    def process_document(self, job_id: str, req_dict: dict, model: str):
        import anthropic as _anthropic
        from app.config import settings
        from app.infra import storage

        client = _anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        start = time.monotonic()

        # I-DOC-09 — structlog `running` transition per ADR-010.
        log.info(
            "asp_doc_job_running",
            tenant_id=req_dict.get("tenant_id"),
            caller_module=req_dict.get("caller_module"),
            job_id=job_id,
            task=req_dict["task"],
        )

        try:
            # Transition: queued → running
            asyncio.run(_async_update_job_status(job_id, "running"))

            file_key = req_dict["payload"]["file_key"]
            file_bytes = storage.download(file_key)

            task = req_dict["task"]

            # I-DOC-06 (ASP-FEAT-ASP-04 v1.0 §8.1) — tracked-document
            # flow. Parse document_id from the tenant-prefixed
            # file_key so subsequent state transitions target the
            # governed `documents` row. Legacy direct-file-key
            # (DEPRECATED §8.3) returns None here; we log + proceed
            # without documents-registry updates so the LogiCRM
            # backward-compatibility contract holds.
            document_id = _document_id_from_file_key(file_key)
            if document_id is None:
                log.warning(
                    "asp_doc_direct_file_key_used",
                    tenant_id=req_dict.get("tenant_id"),
                    caller_module=req_dict.get("caller_module"),
                    job_id=job_id,
                    task=task,
                    file_key_format_mismatch=True,
                    deprecation="v2.0 (per §8.3)",
                )

            # Resolve the async_jobs.id UUID for the FK on
            # documents.extraction_job_id.
            extraction_job_uuid = asyncio.run(
                _async_resolve_asyncjob_id(job_id)
            )

            # I-DOC-07 — OCR pipeline for extract_invoice; generic
            # text extraction for the other two tasks preserves
            # backward compatibility.
            if task == "extract_invoice":
                # Transition: classifying (or pending) → extracting
                if document_id is not None:
                    asyncio.run(_async_update_document_extract_start(
                        document_id, extraction_job_uuid
                    ))
                text_content, page_count = _ocr_pdf(file_bytes)
                text_content = _truncate_tail(text_content, 50_000)
                if not text_content.strip():
                    # §9.4 empty-OCR → job-status-failed with
                    # governed reason. No LLM call made.
                    log.error(
                        "asp_doc_ocr_empty",
                        tenant_id=req_dict.get("tenant_id"),
                        job_id=job_id,
                        document_id=document_id,
                        reason="ocr_empty",
                    )
                    raise RuntimeError("ocr_empty")
            else:
                text_content, page_count = _extract_text(file_bytes, file_key)

            # I-DOC-01 site 3 — async prompt fetch (was sync psycopg2)
            prompt = asyncio.run(_async_fetch_prompt(task, req_dict["caller_module"]))
            system_prompt = (
                prompt["system_prompt"] if prompt
                else f"Extract information from this document. Return JSON."
            )

            # extract_invoice user prompt is the governed minimal
            # {document_text} passthrough (§9.3); other tasks keep
            # the legacy format.
            if task == "extract_invoice":
                user_msg = text_content
            else:
                user_msg = f"Extract from this document:\n{text_content[:8000]}"

            max_tokens = TASK_MAX_TOKENS.get(task, 4096)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )

            from app.services._shared import strip_json
            raw = response.content[0].text
            schema_cls = TASK_OUTPUT_SCHEMAS.get(task)
            if schema_cls:
                output_dict = schema_cls.model_validate_json(strip_json(raw)).model_dump()
                if task == "extract_document":
                    output_dict["page_count"] = page_count
            else:
                output_dict = {"raw": raw}

            # I-DOC-01 site 1 — async job-status update
            asyncio.run(
                _async_update_job_status(job_id, "completed", output_dict)
            )

            # I-DOC-06 / I-DOC-07 — document registry transitions
            # based on task. classify_document updates type +
            # confidence + status=classifying (or preserves terminal).
            # extract_invoice writes extracted_fields + status=complete.
            if document_id is not None:
                if task == "classify_document":
                    try:
                        asyncio.run(_async_update_document_classify(
                            document_id=document_id,
                            document_type=output_dict.get("doc_type"),
                            confidence=output_dict.get("confidence"),
                            extraction_job_uuid=extraction_job_uuid,
                        ))
                    except Exception as doc_exc:
                        log.warning(
                            "asp_doc_registry_update_failed",
                            job_id=job_id, document_id=document_id,
                            task=task, error=str(doc_exc),
                        )
                elif task == "extract_invoice":
                    try:
                        asyncio.run(_async_update_document_extract_complete(
                            document_id=document_id,
                            extracted_fields=output_dict,
                        ))
                    except Exception as doc_exc:
                        log.warning(
                            "asp_doc_registry_update_failed",
                            job_id=job_id, document_id=document_id,
                            task=task, error=str(doc_exc),
                        )
                # extract_document does NOT touch documents — it is
                # the legacy generic-extraction task with no registry
                # contract.

            # I-DOC-08 — ADR-006 cost-emission resilience. Wrap in
            # try/except so a cost-meter failure does not re-raise
            # into the Celery retry path (which would double-count
            # an already-persisted completed job).
            try:
                asyncio.run(_async_emit_cost(job_id, response.usage, model, req_dict))
            except Exception as cost_exc:
                log.warning(
                    "asp_doc_cost_emission_failed",
                    job_id=job_id,
                    tenant_id=req_dict.get("tenant_id"),
                    error=str(cost_exc),
                )

            # I-DOC-09 — structlog `completed` transition.
            duration_ms = int((time.monotonic() - start) * 1000)
            log.info(
                "asp_doc_job_completed",
                tenant_id=req_dict.get("tenant_id"),
                caller_module=req_dict.get("caller_module"),
                job_id=job_id,
                task=task,
                duration_ms=duration_ms,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            # Fire webhook
            asyncio.run(
                _fire_webhook_async(
                    job_id,
                    req_dict["tenant_id"],
                    req_dict["caller_module"],
                    output_dict,
                )
            )

        except Exception as exc:
            # I-DOC-01 site 1 (failure path) — async failure-status
            # update on async_jobs.
            try:
                asyncio.run(_async_update_job_status(job_id, "failed", error=str(exc)))
            except Exception as status_exc:
                # Catastrophic — both the LLM path AND the DB write
                # failed. Log loudly; the retry will try again.
                log.error(
                    "asp_doc_job_status_update_failed",
                    job_id=job_id,
                    primary_error=str(exc),
                    status_update_error=str(status_exc),
                )

            # I-DOC-06 / I-DOC-07 — documents row failure transition
            # (best-effort; never swallows the primary error).
            try:
                file_key_for_fail = req_dict.get("payload", {}).get("file_key", "")
                failure_doc_id = _document_id_from_file_key(file_key_for_fail)
                if failure_doc_id is not None:
                    asyncio.run(_async_update_document_failed(failure_doc_id))
            except Exception as doc_fail_exc:
                log.warning(
                    "asp_doc_registry_failed_update_failed",
                    job_id=job_id, error=str(doc_fail_exc),
                )

            # I-DOC-09 — structlog `failed` transition.
            log.error(
                "asp_doc_job_failed",
                tenant_id=req_dict.get("tenant_id"),
                caller_module=req_dict.get("caller_module"),
                job_id=job_id,
                task=req_dict.get("task"),
                error=str(exc),
                reason=exc.__class__.__name__,
            )
            self.retry(exc=exc, countdown=60)

    return process_document


async def _fire_webhook_async(job_id: str, tenant_id: str, caller_module: str, result: dict) -> None:
    from app.webhook.service import fire_webhook
    await fire_webhook(job_id, tenant_id, caller_module, result)
