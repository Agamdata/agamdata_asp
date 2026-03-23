"""
ASP-04 Doc Intelligence Service (Async)

Supported tasks:
- extract_document
- classify_document

Async flow: Gateway creates job record and dispatches Celery task immediately.
The Celery worker processes the job, then fires the webhook.
"""
import io
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.models.request import InvokeRequest
from app.models.response import JobAcceptedResponse
from app.infra.db import get_session
from app.models.db_models import AsyncJob

log = structlog.get_logger()

VALID_TASKS = {"extract_document", "classify_document"}


# --- Output schemas ---

class ExtractDocumentOutput(BaseModel):
    fields: dict
    tables: list[dict]
    confidence: float
    page_count: int


class ClassifyDocumentOutput(BaseModel):
    doc_type: str
    confidence: float
    suggested_fields: list[str]


TASK_OUTPUT_SCHEMAS = {
    "extract_document": ExtractDocumentOutput,
    "classify_document": ClassifyDocumentOutput,
}


async def handle(req: InvokeRequest, model: str, request_id: str) -> JobAcceptedResponse:
    if req.task not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown doc_intelligence task: {req.task}")

    file_key = req.payload.get("file_key")
    if not file_key:
        raise HTTPException(status_code=400, detail="payload.file_key is required for doc_intelligence")

    # Security: enforce tenant prefix
    expected_prefix = f"{req.tenant_id}/"
    if not file_key.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail=f"file_key must start with {expected_prefix}")

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
    """Extract text from PDF or DOCX. Returns (text, page_count)."""
    if filename.lower().endswith(".docx") or file_bytes[:4] == b"PK\x03\x04":
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
            return text, 1
        except Exception:
            pass

    # Default: treat as PDF
    try:
        from pdfminer.high_level import extract_text as pdf_extract_text
        text = pdf_extract_text(io.BytesIO(file_bytes))
        # Estimate pages by form feed characters
        page_count = max(1, text.count("\x0c") + 1)
        return text, page_count
    except Exception as e:
        log.warning("text_extraction_failed", error=str(e))
        return file_bytes.decode("utf-8", errors="replace"), 1


def _sync_update_job_status(
    job_id: str,
    status: str,
    result: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    import re

    # Use sync driver (replace asyncpg with psycopg2)
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


def _sync_emit_cost(job_id: str, usage, model: str, req_dict: dict) -> None:
    from app.cost.meter import calculate_cost
    import asyncio

    async def _emit():
        from app.cost.meter import emit_cost_event
        await emit_cost_event(
            request_id=job_id,
            tenant_id=req_dict["tenant_id"],
            caller_module=req_dict["caller_module"],
            service_type="doc_intelligence",
            task=req_dict["task"],
            model=model,
            quality_tier=req_dict.get("quality_tier", "standard"),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=calculate_cost(model, usage.input_tokens, usage.output_tokens),
            latency_ms=0,
        )

    asyncio.run(_emit())


def register_task(celery_app):
    @celery_app.task(name="asp.doc_intelligence", bind=True, max_retries=3)
    def process_document(self, job_id: str, req_dict: dict, model: str):
        import anthropic as _anthropic
        from app.config import settings
        from app.infra import storage

        client = _anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        start = time.monotonic()

        try:
            _sync_update_job_status(job_id, "running")

            file_key = req_dict["payload"]["file_key"]
            file_bytes = storage.download(file_key)
            text_content, page_count = _extract_text(file_bytes, file_key)

            task = req_dict["task"]
            from app.registry.prompt_registry import PromptTemplateDTO
            from sqlalchemy import create_engine, text as sql_text
            from sqlalchemy.orm import sessionmaker
            import re

            sync_url = re.sub(r"postgresql\+asyncpg", "postgresql", settings.DATABASE_URL)
            engine = create_engine(sync_url)
            Session = sessionmaker(bind=engine)

            with Session() as session:
                row = session.execute(
                    sql_text("""
                        SELECT system_prompt, user_prompt_template
                        FROM prompt_templates
                        WHERE service_type = 'doc_intelligence'
                          AND task = :task
                          AND caller_module IN (:module, '*')
                          AND is_active = TRUE
                        ORDER BY CASE WHEN caller_module = :module THEN 0 ELSE 1 END
                        LIMIT 1
                    """),
                    {"task": task, "module": req_dict["caller_module"]},
                ).mappings().one_or_none()

            system_prompt = row["system_prompt"] if row else f"Extract information from this document. Return JSON."
            user_msg = f"Extract from this document:\n{text_content[:8000]}"

            response = client.messages.create(
                model=model,
                max_tokens=4096,
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

            _sync_update_job_status(job_id, "completed", output_dict)
            _sync_emit_cost(job_id, response.usage, model, req_dict)

            # Fire webhook
            import asyncio
            asyncio.run(_fire_webhook_async(job_id, req_dict["tenant_id"], req_dict["caller_module"], output_dict))

        except Exception as exc:
            _sync_update_job_status(job_id, "failed", error=str(exc))
            self.retry(exc=exc, countdown=60)

    return process_document


async def _fire_webhook_async(job_id: str, tenant_id: str, caller_module: str, result: dict) -> None:
    from app.webhook.service import fire_webhook
    await fire_webhook(job_id, tenant_id, caller_module, result)
