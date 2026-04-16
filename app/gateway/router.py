import time
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.gateway.auth import verify_api_key
from app.gateway.cost_emitter import emit_cost_event_from_gateway
from app.models.request import InvokeRequest
from app.models.response import InvokeResponse, JobAcceptedResponse, JobStatusResponse
from app.router_model.model_router import resolve_model
from app.services import nlp, generation, doc_intelligence, prediction, dashboard
from app.infra.db import get_session
from app.models.db_models import AsyncJob
from sqlalchemy import select

log = structlog.get_logger()

router = APIRouter()

SERVICE_MAP = {
    "nlp": nlp.handle,
    "generation": generation.handle,
    "doc_intelligence": doc_intelligence.handle,
    "prediction": prediction.handle,
    "dashboard_intelligence": dashboard.handle,
}

# Async services emit their own cost events on completion
ASYNC_SERVICES = {"doc_intelligence", "prediction"}


@router.post("/ai/invoke", response_model=None)
async def invoke(
    req: InvokeRequest,
    tenant=Depends(verify_api_key),
):
    request_id = str(uuid.uuid4())
    model = resolve_model(req.quality_tier)

    log.info(
        "invoke_start",
        request_id=request_id,
        tenant_id=str(tenant.id),
        caller_module=req.caller_module,
        service_type=req.service_type,
        task=req.task,
        model=model,
    )

    handler = SERVICE_MAP.get(req.service_type)
    if not handler:
        raise HTTPException(status_code=422, detail=f"Unknown service_type: '{req.service_type}'. Supported: {sorted(SERVICE_MAP.keys())}")

    # Quota check before invoking LLM
    from app.cost.meter import check_quota
    quota_ok = await check_quota(str(tenant.id), tenant.monthly_quota_usd)
    if not quota_ok:
        raise HTTPException(
            status_code=429,
            detail={"detail": "Monthly quota exceeded", "quota_usd": float(tenant.monthly_quota_usd)},
        )

    start = time.monotonic()
    try:
        result = await handler(req, model, request_id)
    except HTTPException:
        raise
    except Exception as exc:
        log.error(
            "invoke_failed",
            request_id=request_id,
            tenant_id=str(tenant.id),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail={"detail": "Internal error", "request_id": request_id})

    latency_ms = int((time.monotonic() - start) * 1000)

    if req.service_type not in ASYNC_SERVICES:
        try:
            await emit_cost_event_from_gateway(
                request_id=request_id,
                tenant_id=tenant.id,
                caller_module=req.caller_module,
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
            log.error(
                "gateway_cost_emission_failed",
                error=str(e),
                request_id=request_id,
                tenant_id=str(tenant.id),
                caller_module=req.caller_module,
            )
            # ADR-006: cost logging failure must NOT fail the request
            # Response already computed — return it regardless

    log.info(
        "invoke_complete",
        request_id=request_id,
        tenant_id=str(tenant.id),
        latency_ms=latency_ms,
    )
    return result


@router.get("/ai/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, tenant=Depends(verify_api_key)):
    async with get_session() as session:
        result = await session.execute(
            select(AsyncJob).where(
                AsyncJob.job_id == job_id,
                AsyncJob.tenant_id == tenant.id,
            )
        )
        job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        result=job.result_json,
        error=job.error_message,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )
