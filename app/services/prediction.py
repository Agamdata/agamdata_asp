"""
ASP-05 Prediction Service (Async)

Prediction jobs run asynchronously via Celery.
Gateway returns JobAcceptedResponse immediately.
Worker processes and fires webhook on completion.
"""
import json
import time
import uuid

import structlog
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Any

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


def _sync_update_job_status(
    job_id: str,
    status: str,
    result: dict = None,
    error: str = None,
) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    import re

    sync_url = re.sub(r"postgresql\+asyncpg", "postgresql", settings.DATABASE_URL)
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        session.execute(
            text("""
                UPDATE async_jobs
                SET status = :status,
                    result_json = :result,
                    error_message = :error,
                    completed_at = CASE WHEN :status IN ('completed','failed') THEN NOW() ELSE NULL END
                WHERE job_id = :job_id
            """),
            {
                "job_id": job_id,
                "status": status,
                "result": json.dumps(result) if result else None,
                "error": error,
            },
        )
        session.commit()


def register_task(celery_app):
    @celery_app.task(name="asp.prediction", bind=True, max_retries=3)
    def run_prediction(self, job_id: str, req_dict: dict, model: str):
        import anthropic as _anthropic
        from app.config import settings

        client = _anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        try:
            _sync_update_job_status(job_id, "running")

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

            _sync_update_job_status(job_id, "completed", output_dict)

            from app.cost.meter import calculate_cost
            import asyncio

            async def _emit_and_webhook():
                from app.cost.meter import emit_cost_event
                from app.webhook.service import fire_webhook

                await emit_cost_event(
                    request_id=job_id,
                    tenant_id=req_dict["tenant_id"],
                    caller_module=req_dict["caller_module"],
                    service_type="prediction",
                    task=task,
                    model=model,
                    quality_tier=req_dict.get("quality_tier", "standard"),
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    cost_usd=calculate_cost(model, response.usage.input_tokens, response.usage.output_tokens),
                    latency_ms=0,
                )
                await fire_webhook(job_id, req_dict["tenant_id"], req_dict["caller_module"], output_dict)

            asyncio.run(_emit_and_webhook())

        except Exception as exc:
            _sync_update_job_status(job_id, "failed", error=str(exc))
            self.retry(exc=exc, countdown=60)

    return run_prediction
