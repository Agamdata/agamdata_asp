"""
ASP-05 Prediction Service (Async)

Prediction jobs run asynchronously via Celery.
Gateway returns JobAcceptedResponse immediately.
Worker processes and fires webhook on completion.

**ASP-DEFECT-025 fix (2026-04-21, ASP-OUT-064).** Previous
implementation used synchronous `sqlalchemy.create_engine` with
psycopg2 driver derived from `settings.DATABASE_URL` by regex-stripping
`+asyncpg`. psycopg2 was NOT in `requirements.txt` — the Docker image
has only asyncpg. Every ASP-05 Celery task that attempted a DB write
would `ModuleNotFoundError: No module named 'psycopg2'` on first
execution. The bug was latent in pilot because no consumer had driven
the ASP-05 Celery worker end-to-end.

**Fix.** All three DB-touching sites ported to async via
`create_async_engine` + `engine.dispose()` per the DEFECT-022 playbook
(reference implementations: `app/cost/aggregator.py`,
`app/services/doc_intelligence.py`). Same loop-affinity discipline:
per-invocation engine, no pool reuse across `asyncio.run()` boundaries
(ENGINEERING-PLAYBOOK.md §12 Celery task DB-write rule).

Cost-emission path rewritten to use a per-invocation engine + direct
`INSERT INTO cost_events` SQL, bypassing the shared-pool
`emit_cost_event` helper — same fix pattern as
`doc_intelligence._async_emit_cost` (I-DOC-11 commit `1ccf85b`).
"""
import asyncio
import json
import time
import uuid
from typing import Any, Optional

import structlog
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.request import InvokeRequest
from app.models.response import JobAcceptedResponse
from app.infra.db import get_session
from app.models.db_models import AsyncJob

log = structlog.get_logger()

VALID_TASKS = {
    "churn_prediction",
    "revenue_forecast",
    "anomaly_detection",
    "lead_scoring",
}


class PredictionOutput(BaseModel):
    scores: dict[str, Any]
    explanation: str
    confidence: float
    metadata: dict[str, Any] = {}


async def handle(req: InvokeRequest, model: str, request_id: str) -> JobAcceptedResponse:
    if req.task not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown prediction task: {req.task}")

    job_id = str(uuid.uuid4())
    async with get_session() as session:
        job = AsyncJob(
            job_id=job_id,
            tenant_id=uuid.UUID(req.tenant_id),
            caller_module=req.caller_module,
            service_type="prediction",
            task=req.task,
            status="queued",
        )
        session.add(job)
        await session.commit()

    from app.worker import celery_app
    celery_app.send_task(
        "asp.prediction",
        args=[job_id, req.model_dump(), model],
    )

    log.info("prediction_queued", request_id=request_id, job_id=job_id,
             tenant_id=req.tenant_id, task=req.task)

    return JobAcceptedResponse(
        request_id=request_id,
        job_id=job_id,
        status="queued",
        message="Prediction job accepted. Poll GET /api/v1/ai/jobs/{job_id} or await webhook.",
    )


# ──────────────────────────────────────────────────────────────────────
# DEFECT-025 fix — ASYNC DB HELPERS (asyncpg, per-invocation engine)
# ──────────────────────────────────────────────────────────────────────
#
# Governed by ENGINEERING-PLAYBOOK.md §12 Celery task DB-write rule.
# Each helper below creates a fresh async engine scoped to its call and
# disposes it before returning. Celery tasks wrap each helper in its
# own `asyncio.run()`, which creates a new event loop per invocation —
# so no pool can be shared across invocations.


async def _async_update_job_status(
    job_id: str,
    status: str,
    result: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    """Update `async_jobs` row for this job.

    Implementation note (same as `doc_intelligence._async_update_job_status`):
    the terminal-state guard is computed in Python rather than via SQL
    `CASE` so the SQL statement uses each bind parameter in exactly
    one positional context. asyncpg strictly infers parameter types
    positionally and rejects inconsistent-type deductions when the
    same placeholder is used in both a VARCHAR-column assignment and
    a string-literal comparison (raises `AmbiguousParameterError`).
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


async def _async_emit_cost(job_id: str, usage, model: str, req_dict: dict,
                            service_type: str, task: str) -> None:
    """Emit a cost_events row for this LLM call via a per-invocation
    engine + direct INSERT. Governed by ENGINEERING-PLAYBOOK.md §12:
    do NOT call `app.cost.meter.emit_cost_event` from inside
    `asyncio.run()` — the shared pool there will race loop affinity.

    Pattern mirrors `doc_intelligence._async_emit_cost` exactly.
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
                       :service, :task, :model, :tier,
                       :inp, :out, :cost,
                       :lat, 'success', NULL, NOW())
                """),
                {
                    "req":     uuid.UUID(job_id) if isinstance(job_id, str) else job_id,
                    "tenant":  uuid.UUID(req_dict["tenant_id"])
                               if isinstance(req_dict["tenant_id"], str)
                               else req_dict["tenant_id"],
                    "caller":  req_dict["caller_module"],
                    "cfeat":   req_dict.get("caller_feature"),
                    "service": service_type,
                    "task":    task,
                    "model":   model,
                    "tier":    req_dict.get("quality_tier", "standard"),
                    "inp":     usage.input_tokens,
                    "out":     usage.output_tokens,
                    "cost":    cost_usd,
                    "lat":     0,
                },
            )
    finally:
        await engine.dispose()


async def _fire_webhook_async(job_id: str, tenant_id: str, caller_module: str,
                                result: dict) -> None:
    """Webhook dispatch wrapper — isolated so the test suite can
    patch it to a no-op (same approach as doc_intelligence)."""
    from app.webhook.service import fire_webhook
    await fire_webhook(job_id, tenant_id, caller_module, result)


def register_task(celery_app):
    @celery_app.task(name="asp.prediction", bind=True, max_retries=3)
    def run_prediction(self, job_id: str, req_dict: dict, model: str):
        import anthropic as _anthropic
        from app.config import settings

        client = _anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        start = time.monotonic()

        # ADR-010 — running transition event
        log.info(
            "asp_prediction_job_running",
            tenant_id=req_dict.get("tenant_id"),
            caller_module=req_dict.get("caller_module"),
            job_id=job_id,
            task=req_dict["task"],
        )

        try:
            # Transition: queued → running (per-invocation async engine)
            asyncio.run(_async_update_job_status(job_id, "running"))

            task = req_dict["task"]
            payload = req_dict["payload"]

            system_prompt = (
                f"You are a predictive analytics engine for a logistics CRM. "
                f"Perform {task} analysis. "
                f"Return ONLY JSON: {{\"scores\": {{...}}, \"explanation\": string, "
                f"\"confidence\": float, \"metadata\": {{...}}}}"
            )
            user_msg = f"Analyse this data for {task}:\n{json.dumps(payload)}"

            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            from app.services._shared import strip_json
            raw = response.content[0].text
            output_dict = PredictionOutput.model_validate_json(strip_json(raw)).model_dump()

            # Transition: running → completed (per-invocation async engine)
            asyncio.run(_async_update_job_status(job_id, "completed", output_dict))

            # ADR-006 — cost emission wrapped in try/except. Per
            # ENGINEERING-PLAYBOOK.md §12 Celery task DB-write rule, the
            # emission uses a per-invocation engine (_async_emit_cost)
            # rather than the shared-pool emit_cost_event helper.
            try:
                asyncio.run(
                    _async_emit_cost(
                        job_id, response.usage, model, req_dict,
                        service_type="prediction", task=task,
                    )
                )
            except Exception as cost_exc:
                log.warning(
                    "asp_prediction_cost_emission_failed",
                    job_id=job_id,
                    tenant_id=req_dict.get("tenant_id"),
                    error=str(cost_exc),
                )

            # ADR-010 — completed transition event
            duration_ms = int((time.monotonic() - start) * 1000)
            log.info(
                "asp_prediction_job_completed",
                tenant_id=req_dict.get("tenant_id"),
                caller_module=req_dict.get("caller_module"),
                job_id=job_id,
                task=task,
                duration_ms=duration_ms,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            # Fire webhook (isolated async function; uses its own
            # loop via asyncio.run so it does not reuse the cost
            # emission loop's pool).
            asyncio.run(
                _fire_webhook_async(
                    job_id, req_dict["tenant_id"], req_dict["caller_module"],
                    output_dict,
                )
            )

        except Exception as exc:
            # Failure-path: per-invocation async update (was sync psycopg2)
            try:
                asyncio.run(_async_update_job_status(job_id, "failed", error=str(exc)))
            except Exception as status_exc:
                log.error(
                    "asp_prediction_status_update_failed",
                    job_id=job_id,
                    primary_error=str(exc),
                    status_update_error=str(status_exc),
                )

            log.error(
                "asp_prediction_job_failed",
                tenant_id=req_dict.get("tenant_id"),
                caller_module=req_dict.get("caller_module"),
                job_id=job_id,
                task=req_dict.get("task"),
                error=str(exc),
                reason=exc.__class__.__name__,
            )
            self.retry(exc=exc, countdown=60)

    return run_prediction
