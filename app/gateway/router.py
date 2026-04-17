"""Gateway router — ASP-FEAT-ASP-00 v1.0.

Routes POST /ai/invoke and GET /ai/jobs/{job_id}. Auth via dual-path
verify_api_key (§10 I-04). Rate limiting is wired in Phase 4 (I-08).
Capabilities and schemas endpoints are added in Phase 4 (I-09, I-10).

Key observability invariants (§11 I-06, I-13):
  - request_id allocated at the top of the handler, bound to
    request.state.request_id so the global exception handler can render it
    in the RFC 7807 envelope.
  - structlog contextvars bound via bind_contextvars() with request_id,
    tenant_id, caller_module, caller_feature — every downstream log event
    within the same request carries these fields automatically. Cleared
    at the end of the handler via clear_contextvars().
  - X-Request-Id response header mirrors the body request_id (I-13).
    Injected via ASGI middleware (app.main) so it lands on both success
    and error responses uniformly.

Async behaviour (§11 I-11):
  - service_type in ASYNC_SERVICES returns HTTP 202 + JobAcceptedResponse.
  - Sync services return HTTP 200 + InvokeResponse.

Cross-tenant 404 (§11 I-12):
  - GET /ai/jobs/{job_id} filters WHERE job_id = ? AND tenant_id = ?.
  - Missing or cross-tenant job returns 404 (never 403) per ADR-012.
"""
import time
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.gateway.auth import verify_api_key
from app.gateway.cost_emitter import emit_cost_event_from_gateway
from app.gateway.middleware.rate_limiter import INVOKE_RATE, JOBS_RATE, limiter
from app.infra.db import get_session
from app.models.db_models import AsyncJob
from app.models.request import InvokeRequest
from app.models.response import (
    InvokeResponse,
    JobAcceptedResponse,
    JobStatusResponse,
)
from app.router_model.model_router import resolve_model
from app.services import dashboard, doc_intelligence, generation, nlp, prediction

log = structlog.get_logger()

router = APIRouter()

SERVICE_MAP = {
    "nlp": nlp.handle,
    "generation": generation.handle,
    "doc_intelligence": doc_intelligence.handle,
    "prediction": prediction.handle,
    "dashboard_intelligence": dashboard.handle,
}

# Async services emit their own cost events on completion (§4, §11 I-11).
ASYNC_SERVICES = {"doc_intelligence", "prediction"}


@router.post("/ai/invoke", response_model=None)
@limiter.limit(INVOKE_RATE)   # I-08 — per-tenant RPM; dormant when disabled
async def invoke(
    request: Request,
    req: InvokeRequest,
    tenant=Depends(verify_api_key),
):
    request_id = str(uuid.uuid4())
    # I-13 — expose request_id to exception handler and response-header
    # middleware via request.state.
    request.state.request_id = request_id
    # I-08 — expose tenant_id so the rate limiter key function finds it
    # (post-auth; the decorator evaluates key_func on the incoming request).
    request.state.tenant_id = str(tenant.id)

    model = resolve_model(req.quality_tier)

    # I-06 — bind request-wide context so EVERY subsequent structlog event
    # in this request carries these fields automatically. Cleared at end of
    # handler via clear_contextvars().
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        tenant_id=str(tenant.id),
        caller_module=req.caller_module,
        caller_feature=req.caller_feature,   # may be None; structlog emits as null
        service_type=req.service_type,
        task=req.task,
    )

    log.info("invoke_start", model=model)

    try:
        handler = SERVICE_MAP.get(req.service_type)
        if not handler:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unknown service_type: '{req.service_type}'. "
                    f"Supported: {sorted(SERVICE_MAP.keys())}"
                ),
            )

        # Quota check before invoking LLM
        from app.cost.meter import check_quota
        quota_ok = await check_quota(str(tenant.id), tenant.monthly_quota_usd)
        if not quota_ok:
            log.warning("quota_exceeded", quota_usd=float(tenant.monthly_quota_usd))
            raise HTTPException(
                status_code=429,
                detail="Monthly quota exceeded",
            )

        start = time.monotonic()
        try:
            result = await handler(req, model, request_id)
        except HTTPException:
            raise
        except Exception as exc:
            log.error("invoke_failed", error=str(exc), exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Internal error",
            )
        latency_ms = int((time.monotonic() - start) * 1000)

        # I-07 — caller_feature threaded into cost event for sync services.
        # Async services self-emit in Celery with their own caller_feature
        # propagation.
        if req.service_type not in ASYNC_SERVICES:
            try:
                await emit_cost_event_from_gateway(
                    request_id=request_id,
                    tenant_id=tenant.id,
                    caller_module=req.caller_module,
                    caller_feature=req.caller_feature,
                    service_type=req.service_type,
                    task=req.task,
                    model=model,
                    quality_tier=req.quality_tier,
                    input_tokens=result.meta.input_tokens,
                    output_tokens=result.meta.output_tokens,
                    cost_usd=result.meta.cost_usd,
                    latency_ms=latency_ms,
                )
            except Exception as e:
                # ADR-006 / DEFECT-020 — cost emission must not fail the request.
                log.error("gateway_cost_emission_failed", error=str(e))

        log.info("invoke_complete", latency_ms=latency_ms)

        # I-11 — 202 for async, 200 for sync. Use JSONResponse so we can
        # set status_code explicitly (response_model=None on the route).
        if req.service_type in ASYNC_SERVICES:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=result.model_dump() if hasattr(result, "model_dump") else result.dict(),
            )
        return result
    finally:
        # Always clear so we do not leak context into the next request
        # served by this worker.
        structlog.contextvars.clear_contextvars()


@router.get("/ai/jobs/{job_id}", response_model=JobStatusResponse)
@limiter.limit(JOBS_RATE)   # I-08 — per-tenant RPM; dormant when disabled
async def get_job_status(
    request: Request,
    job_id: str,
    tenant=Depends(verify_api_key),
):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.tenant_id = str(tenant.id)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        tenant_id=str(tenant.id),
        job_id=job_id,
    )
    try:
        async with get_session() as session:
            result = await session.execute(
                select(AsyncJob).where(
                    AsyncJob.job_id == job_id,
                    AsyncJob.tenant_id == tenant.id,   # I-12 — tenant scope
                )
            )
            job = result.scalar_one_or_none()

        if not job:
            # I-12 — cross-tenant or nonexistent: 404 always, never 403.
            log.info("job_not_found")
            raise HTTPException(status_code=404, detail="Job not found")

        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            result=job.result_json,
            error=job.error_message,
            created_at=job.created_at.isoformat(),
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
        )
    finally:
        structlog.contextvars.clear_contextvars()
