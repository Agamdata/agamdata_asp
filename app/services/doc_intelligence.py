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

VALID_TASKS = {"extract_document", "classify_document"}


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
    """Emit a cost_events row for this LLM call. Wrapped in try/except
    at the Celery-task boundary per ADR-006 (I-DOC-08 bundled) — any
    failure here MUST NOT break the response path."""
    from app.cost.meter import calculate_cost, emit_cost_event

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
            text_content, page_count = _extract_text(file_bytes, file_key)

            task = req_dict["task"]

            # I-DOC-01 site 3 — async prompt fetch (was sync psycopg2)
            prompt = asyncio.run(_async_fetch_prompt(task, req_dict["caller_module"]))
            system_prompt = (
                prompt["system_prompt"] if prompt
                else f"Extract information from this document. Return JSON."
            )
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

            # I-DOC-01 site 1 — async job-status update (was sync psycopg2)
            asyncio.run(
                _async_update_job_status(job_id, "completed", output_dict)
            )

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
            # update (was sync psycopg2 via the same helper).
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
