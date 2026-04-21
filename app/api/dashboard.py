"""
ASP-FEAT-ASP-04 v1.0 §6.4 — dashboard UI router (I-DOC-10).

Server-rendered Jinja2 + HTMX. Same-origin with the API surface
(no CORS introduced). CSP header middleware applied per-route to
honour §10.3.

Endpoints:
  GET  /dashboard/login                               → login form
  POST /dashboard/login                               → validate key + set cookie + redirect
  GET  /dashboard                                     → redirects to doc-intelligence
  GET  /dashboard/doc-intelligence                    → two-panel layout
  POST /dashboard/doc-intelligence/upload             → proxies §6.1 upload, returns _upload_panel partial
  GET  /dashboard/doc-intelligence/status/{doc_id}    → HTMX polling; returns _review_panel partial when ready
  GET  /dashboard/doc-intelligence/pdf/{doc_id}       → tenant-scoped PDF proxy from MinIO

**Auth evolution (ASP-OUT-075 pilot-demo unblock).** Browsers cannot
set the `X-ASP-API-Key` header on navigation requests. Added a
cookie-based session flow — login form validates the key server-side
and sets `asp_session` cookie (HttpOnly, SameSite=Lax, 1-hour TTL).
Protected dashboard routes check the cookie first, fall back to the
header, and redirect to `/dashboard/login` when neither is present
(instead of 401). The API surface under `/api/v1/*` is untouched;
cookie auth is dashboard-only.

**v1.1 security item** (recorded in ASP-FEAT-ASP-04 v1.0 §14): the
raw API key in the cookie is a pilot-only concession. Production
Atrium must replace with a server-side session token that maps to
the key, never storing the key itself in a browser-accessible
surface.
"""
from __future__ import annotations

import io
from typing import Optional

import structlog
from fastapi import (
    APIRouter, Cookie, Depends, File, Form, Header, HTTPException, Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.documents import upload_document as _upload_impl
from app.config import settings
from app.gateway.auth import verify_api_key
from app.infra import storage


# Session-cookie governance (ASP-OUT-075)
_SESSION_COOKIE_NAME = "asp_session"
_SESSION_MAX_AGE_SECONDS = 3600   # 1 hour per directive
_LOGIN_PATH = "/dashboard/login"


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
# Cookie-aware auth dependency (ASP-OUT-075)
#
# Browsers cannot set `X-ASP-API-Key` on navigation requests, so the
# dashboard needs its own auth surface. This dependency:
#   1. Reads the `asp_session` cookie (raw API key, per pilot
#      concession — see v1.1 security note in ASP-FEAT-ASP-04 §14).
#   2. Falls back to `X-ASP-API-Key` header for programmatic callers.
#   3. When neither is present → raises a **redirect** to the login
#      form (303 See Other with `Location: /dashboard/login`) instead
#      of 401. HTMX-originated requests can still be redirected cleanly
#      (HTMX follows 3xx redirects when the redirected URL is
#      same-origin).
#   4. When a key is present but `verify_api_key` rejects it → the
#      underlying 401 propagates AND the invalid cookie is cleared via
#      `Set-Cookie` so the next navigation re-prompts login.
#
# This dependency is used for dashboard routes ONLY. The `/api/v1/*`
# surface keeps the existing header-only `verify_api_key` contract.
# ---------------------------------------------------------------------------

async def dashboard_auth(
    request: Request,
    asp_session: Optional[str] = Cookie(default=None, alias=_SESSION_COOKIE_NAME),
    x_asp_api_key: Optional[str] = Header(default=None, alias="X-ASP-API-Key"),
):
    """Cookie-first auth for dashboard routes; redirect-to-login on miss."""
    key = asp_session or x_asp_api_key
    if not key:
        # No credentials → redirect to login (303 See Other).
        raise HTTPException(
            status_code=303,
            headers={"Location": _LOGIN_PATH},
        )

    try:
        tenant = await verify_api_key(request=request, x_asp_api_key=key)
    except HTTPException as e:
        # Invalid key — clear the stale cookie so next navigation
        # re-prompts login.
        if asp_session is not None:
            resp = RedirectResponse(
                url=_LOGIN_PATH + "?expired=1",
                status_code=303,
            )
            resp.delete_cookie(_SESSION_COOKIE_NAME)
            raise HTTPException(
                status_code=303,
                headers={
                    "Location": _LOGIN_PATH + "?expired=1",
                    "Set-Cookie": f"{_SESSION_COOKIE_NAME}=; Max-Age=0; "
                                  f"HttpOnly; SameSite=Lax; Path=/",
                },
            ) from e
        # Header-only path (programmatic caller) — propagate 401
        # verbatim with the original verify_api_key envelope.
        raise

    return tenant


# ---------------------------------------------------------------------------
# Login surface (ASP-OUT-075)
# ---------------------------------------------------------------------------

@router.get("/dashboard/login", response_class=HTMLResponse)
async def dashboard_login_form(request: Request, expired: Optional[str] = None):
    """Render the login form. `?expired=1` surfaces a session-expired
    message after a cookie clear."""
    error = None
    if expired:
        error = "Your session expired or the API key was invalidated. Please sign in again."
    resp = templates.TemplateResponse(
        "dashboard/login.html",
        {"request": request, "error": error},
    )
    # CSP applied so the login page's <script> blocks (none in v1.0,
    # but the base.html HTMX + pdf.js CDN loads are governed under
    # the same policy) are covered.
    return _apply_csp(resp)


@router.post("/dashboard/login")
async def dashboard_login_submit(
    request: Request,
    api_key: str = Form(...),
):
    """Validate the submitted API key and, on success, set the
    `asp_session` cookie and redirect to `/dashboard/doc-intelligence`.
    On failure, re-render the login form with an error message and a
    400-status (no cookie set)."""
    try:
        tenant = await verify_api_key(request=request, x_asp_api_key=api_key)
    except HTTPException:
        resp = templates.TemplateResponse(
            "dashboard/login.html",
            {
                "request": request,
                "error": "Invalid API key. Check the value and try again.",
            },
            status_code=400,
        )
        return _apply_csp(resp)

    # Success — set cookie + redirect.
    redirect = RedirectResponse(
        url="/dashboard/doc-intelligence",
        status_code=303,
    )
    redirect.set_cookie(
        key=_SESSION_COOKIE_NAME,
        value=api_key,
        max_age=_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,    # pilot — HTTP only per directive
        path="/",
    )
    log.info(
        "asp_dashboard_login_succeeded",
        tenant_id=str(tenant.id),
        max_age_seconds=_SESSION_MAX_AGE_SECONDS,
    )
    # Apply CSP on the redirect too (defence-in-depth).
    redirect.headers["Content-Security-Policy"] = _CSP_POLICY
    return redirect


# ---------------------------------------------------------------------------
# Dashboard root (cookie-aware)
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_root(request: Request, tenant=Depends(dashboard_auth)):
    resp = templates.TemplateResponse(
        "dashboard/doc_intelligence.html",
        {"request": request, "tenant_id": str(tenant.id)},
    )
    return _apply_csp(resp)


@router.get("/dashboard/doc-intelligence", response_class=HTMLResponse)
async def dashboard_doc_intel(request: Request, tenant=Depends(dashboard_auth)):
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
    tenant=Depends(dashboard_auth),
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
    request: Request, document_id: str, tenant=Depends(dashboard_auth),
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
async def dashboard_pdf(document_id: str, tenant=Depends(dashboard_auth)):
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
