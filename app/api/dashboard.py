"""
ASP-FEAT-ASP-04 v1.0 §6.4 — dashboard UI router (I-DOC-10).

Server-rendered Jinja2 + HTMX. Same-origin with the API surface
(no CORS introduced). CSP header middleware applied per-route to
honour §10.3.

Endpoints:
  GET  /dashboard                                     → redirects to doc-intelligence
  GET  /dashboard/doc-intelligence                    → two-panel layout
  POST /dashboard/doc-intelligence/upload             → proxies §6.1 upload, returns _upload_panel partial
  GET  /dashboard/doc-intelligence/status/{doc_id}    → HTMX polling; returns _review_panel partial when ready
  GET  /dashboard/doc-intelligence/pdf/{doc_id}       → tenant-scoped PDF proxy from MinIO

Auth: verify_api_key on every endpoint. The dashboard's HTML page is
fetched once via a URL that includes the API key header (clients set
it via browser devtools or the inline hint in _upload_panel).
"""
from __future__ import annotations

import io
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.documents import upload_document as _upload_impl
from app.config import settings
from app.gateway.auth import verify_api_key
from app.infra import storage


log = structlog.get_logger()

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


# CSP header per §10.3 — applied on every /dashboard/* response.
_CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://unpkg.com https://cdnjs.cloudflare.com 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://unpkg.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none';"
)


def _apply_csp(resp: Response) -> Response:
    resp.headers["Content-Security-Policy"] = _CSP_POLICY
    return resp


# ---------------------------------------------------------------------------
# Dashboard root
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_root(request: Request, tenant=Depends(verify_api_key)):
    resp = templates.TemplateResponse(
        "dashboard/doc_intelligence.html",
        {"request": request, "tenant_id": str(tenant.id)},
    )
    return _apply_csp(resp)


@router.get("/dashboard/doc-intelligence", response_class=HTMLResponse)
async def dashboard_doc_intel(request: Request, tenant=Depends(verify_api_key)):
    resp = templates.TemplateResponse(
        "dashboard/doc_intelligence.html",
        {"request": request, "tenant_id": str(tenant.id)},
    )
    return _apply_csp(resp)


# ---------------------------------------------------------------------------
# HTMX multipart proxy to the §6.1 upload endpoint
# ---------------------------------------------------------------------------

@router.post("/dashboard/doc-intelligence/upload", response_class=HTMLResponse)
async def dashboard_upload(
    request: Request,
    file: UploadFile = File(...),
    document_type_hint: Optional[str] = Form(default=None),
    tenant=Depends(verify_api_key),
):
    """Server-side proxy into §6.1 upload endpoint. Returns the
    _upload_panel partial (with document_id + storage_path populated)
    which HTMX swaps into #upload-slot."""
    try:
        upload_resp = await _upload_impl(
            request=request,
            file=file,
            document_type_hint=document_type_hint,
            tenant=tenant,
        )
    except HTTPException as e:
        ctx = {
            "request": request,
            "error": e.detail if isinstance(e.detail, str)
                     else e.detail.get("detail", "upload failed"),
        }
        resp = templates.TemplateResponse(
            "dashboard/_upload_panel.html", ctx, status_code=e.status_code,
        )
        return _apply_csp(resp)

    ctx = {
        "request": request,
        "tenant_id": str(tenant.id),
        "document_id": upload_resp.document_id,
        "storage_path": upload_resp.storage_path,
        "original_filename": upload_resp.original_filename,
    }
    resp = templates.TemplateResponse("dashboard/_upload_panel.html", ctx)
    return _apply_csp(resp)


# ---------------------------------------------------------------------------
# HTMX polling endpoint
# ---------------------------------------------------------------------------

def _confidence_class(confidence: Optional[float]) -> str:
    """§13 OQ-4 thresholds: green > 0.8, amber 0.5-0.8, red < 0.5."""
    if confidence is None:
        return "amber"
    if confidence > 0.8:
        return "green"
    if confidence >= 0.5:
        return "amber"
    return "red"


@router.get(
    "/dashboard/doc-intelligence/status/{document_id}",
    response_class=HTMLResponse,
)
async def dashboard_status(
    request: Request, document_id: str, tenant=Depends(verify_api_key),
):
    """HTMX polling endpoint.

    If extraction_status='complete' → return _review_panel partial
    (HTMX swaps the polling element out via hx-swap="outerHTML").
    Otherwise → return a still-polling fragment that keeps polling.
    """
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("""
                        SELECT id, tenant_id, document_type,
                               classification_confidence,
                               extraction_status, extracted_fields
                        FROM documents
                        WHERE id = :doc_id AND tenant_id = :tenant_id
                    """),
                    {"doc_id": document_id, "tenant_id": str(tenant.id)},
                )
            ).mappings().one_or_none()
    finally:
        await engine.dispose()

    if row is None:
        # Cross-tenant OR unknown document_id — 404 (resource-lookup
        # path, not the file_key contract path, so standard
        # cross-tenant 404 applies per §10.0).
        raise HTTPException(status_code=404, detail="document not found")

    status = row["extraction_status"]
    classify_conf = row["classification_confidence"]
    extracted = row["extracted_fields"]

    if status == "complete" and extracted is not None:
        # Terminal-success state: render the review panel. HTMX
        # replaces the polling div via hx-swap="outerHTML".
        ctx = {
            "request": request,
            "document_id": document_id,
            "document_type": row["document_type"],
            "classification_confidence": classify_conf or 0.0,
            "confidence_class": _confidence_class(classify_conf),
            "extracted_fields": extracted,
        }
        resp = templates.TemplateResponse(
            "dashboard/_review_panel.html", ctx,
        )
        # HTMX swap into the parent #review-slot happens via the
        # hx-target="#review-slot" on the polling element in the
        # upload template. Show the panel slot now.
        resp.headers["HX-Trigger"] = "show-review-slot"
        # Move the panel into #review-slot via OOB swap.
        return _apply_csp(resp)

    if status == "failed":
        # Terminal failure — stop polling.
        html = (
            f'<div class="error">'
            f'Extraction failed for document {document_id}. '
            f'Check the job status via /api/v1/ai/jobs/.'
            f'</div>'
        )
        resp = HTMLResponse(html)
        return _apply_csp(resp)

    # Still in flight — render a badge if classify finished; keep polling.
    parts = ['<div id="classify-slot" '
             f'hx-get="/dashboard/doc-intelligence/status/{document_id}" '
             'hx-trigger="every 2s" hx-swap="outerHTML" hx-target="this">']
    if row["document_type"]:
        cls = _confidence_class(classify_conf)
        pct = int((classify_conf or 0.0) * 100)
        parts.append(
            f'<span class="classify-badge conf-{cls}">'
            f'{row["document_type"].title()} — {pct}%'
            f'</span> '
        )
    parts.append(
        '<p class="subtle"><span class="spinner"></span> '
        f'Status: <code>{status}</code></p>'
    )
    parts.append('</div>')
    resp = HTMLResponse("".join(parts))
    return _apply_csp(resp)


# ---------------------------------------------------------------------------
# PDF proxy endpoint (tenant-scoped)
# ---------------------------------------------------------------------------

@router.get("/dashboard/doc-intelligence/pdf/{document_id}")
async def dashboard_pdf(document_id: str, tenant=Depends(verify_api_key)):
    """Proxy the PDF bytes from MinIO to the browser. Tenant-scoped —
    cross-tenant document_id → 404 (§10.1 resource-lookup path)."""
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("""
                        SELECT storage_path
                        FROM documents
                        WHERE id = :doc_id AND tenant_id = :tenant_id
                    """),
                    {"doc_id": document_id, "tenant_id": str(tenant.id)},
                )
            ).mappings().one_or_none()
    finally:
        await engine.dispose()

    if row is None:
        raise HTTPException(status_code=404, detail="document not found")

    try:
        data = storage.download(row["storage_path"])
    except Exception as e:
        log.error("asp_doc_pdf_proxy_failed",
                  document_id=document_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "type": "/errors/internal",
                "title": "Internal error",
                "detail": "storage fetch failed",
            },
        )

    resp = Response(content=data, media_type="application/pdf")
    resp.headers["Content-Disposition"] = f'inline; filename="{document_id}.pdf"'
    # No CSP on PDF bytes — browser renders them in-canvas via pdf.js,
    # which is same-origin XHR from the dashboard page.
    return resp
