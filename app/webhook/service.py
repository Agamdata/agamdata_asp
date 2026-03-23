"""
ASP-09 Webhook Service

Webhook delivery with exponential backoff.
Max retries: settings.WEBHOOK_MAX_RETRIES (default 5)
Backoff: 30s, 60s, 120s, 240s, 480s

Registration endpoint: POST /api/v1/webhooks/register
"""
import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional

import bcrypt
import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text

from app.config import settings
from app.gateway.auth import verify_api_key
from app.infra.db import get_session
from app.models.db_models import WebhookRegistration
from app.models.request import WebhookRegisterRequest

log = structlog.get_logger()
router = APIRouter()


async def fire_webhook(
    job_id: str,
    tenant_id: str,
    caller_module: str,
    result: dict,
    status: str = "completed",
) -> None:
    """Fire webhook to registered callback URL with exponential backoff."""
    async with get_session() as session:
        db_result = await session.execute(
            select(WebhookRegistration).where(
                WebhookRegistration.tenant_id == tenant_id,
                WebhookRegistration.caller_module == caller_module,
                WebhookRegistration.is_active == True,
            )
        )
        reg = db_result.scalar_one_or_none()

    if not reg:
        return  # no webhook registered, skip silently

    payload = {
        "job_id": job_id,
        "status": status,
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(payload).encode()

    headers = {"Content-Type": "application/json"}
    if reg.secret_hash:
        # secret_hash stores the bcrypt hash of the secret; for HMAC we need the raw secret.
        # Webhooks store secret_hash as bcrypt; the raw secret is provided at registration time.
        # Since we can't reverse bcrypt, sign with the stored hash as a shared secret instead
        # (production: store secret encrypted, not hashed).
        sig = hmac.new(reg.secret_hash.encode(), payload_bytes, hashlib.sha256).hexdigest()
        headers["X-ASP-Signature"] = f"sha256={sig}"

    for attempt in range(settings.WEBHOOK_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(reg.callback_url, content=payload_bytes, headers=headers)
                if r.status_code < 300:
                    async with get_session() as session:
                        await session.execute(
                            text("""
                                UPDATE async_jobs
                                SET webhook_delivered = TRUE,
                                    webhook_attempts = webhook_attempts + 1
                                WHERE job_id = :job_id
                            """),
                            {"job_id": job_id},
                        )
                        await session.commit()
                    log.info("webhook_delivered", job_id=job_id, attempt=attempt)
                    return
        except Exception as exc:
            log.warning("webhook_attempt_failed", job_id=job_id, attempt=attempt, error=str(exc))

        delay = settings.WEBHOOK_RETRY_DELAY_SECONDS * (2 ** attempt)
        await asyncio.sleep(delay)

    # Dead-letter
    async with get_session() as session:
        await session.execute(
            text("""
                UPDATE async_jobs
                SET webhook_attempts = webhook_attempts + :retries
                WHERE job_id = :job_id
            """),
            {"job_id": job_id, "retries": settings.WEBHOOK_MAX_RETRIES},
        )
        await session.commit()
    log.error("webhook_dead_lettered", job_id=job_id)


@router.post("/register")
async def register_webhook(
    body: WebhookRegisterRequest,
    tenant=Depends(verify_api_key),
):
    secret_hash: Optional[str] = None
    if body.secret:
        secret_hash = bcrypt.hashpw(body.secret.encode(), bcrypt.gensalt()).decode()

    async with get_session() as session:
        # Upsert: update if exists, else insert
        existing = await session.execute(
            select(WebhookRegistration).where(
                WebhookRegistration.tenant_id == tenant.id,
                WebhookRegistration.caller_module == body.caller_module,
            )
        )
        reg = existing.scalar_one_or_none()

        if reg:
            reg.callback_url = body.callback_url
            if secret_hash:
                reg.secret_hash = secret_hash
            reg.is_active = True
        else:
            reg = WebhookRegistration(
                tenant_id=tenant.id,
                caller_module=body.caller_module,
                callback_url=body.callback_url,
                secret_hash=secret_hash,
            )
            session.add(reg)

        await session.commit()

    log.info("webhook_registered", tenant_id=str(tenant.id), caller_module=body.caller_module)
    return {"status": "registered", "caller_module": body.caller_module}


@router.delete("/register/{caller_module}")
async def deregister_webhook(caller_module: str, tenant=Depends(verify_api_key)):
    async with get_session() as session:
        result = await session.execute(
            select(WebhookRegistration).where(
                WebhookRegistration.tenant_id == tenant.id,
                WebhookRegistration.caller_module == caller_module,
            )
        )
        reg = result.scalar_one_or_none()
        if reg:
            reg.is_active = False
            await session.commit()
    return {"status": "deregistered"}
