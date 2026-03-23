"""
ASP-08 Cost Meter

Called by Gateway after every synchronous service call.
Called by async Celery tasks after job completion.
MUST NOT raise an exception — wrap in try/except and log only.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.infra.db import get_session
from app.models.db_models import CostEvent, Tenant

log = structlog.get_logger()

router = APIRouter()

# Anthropic pricing per million tokens (USD) — approximate, update as needed
_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6":         {"input": 3.00, "output": 15.00},
    "claude-opus-4-6":           {"input": 15.00, "output": 75.00},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = _PRICING.get(model, {"input": 3.00, "output": 15.00})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


async def emit_cost_event(**kwargs) -> None:
    try:
        async with get_session() as session:
            model = kwargs.get("model", "")
            input_tokens = kwargs.get("input_tokens", 0)
            output_tokens = kwargs.get("output_tokens", 0)
            cost_usd = kwargs.get("cost_usd") or calculate_cost(model, input_tokens, output_tokens)

            event = CostEvent(
                request_id=uuid.UUID(kwargs["request_id"]) if isinstance(kwargs["request_id"], str) else kwargs["request_id"],
                tenant_id=uuid.UUID(kwargs["tenant_id"]) if isinstance(kwargs["tenant_id"], str) else kwargs["tenant_id"],
                caller_module=kwargs["caller_module"],
                service_type=kwargs["service_type"],
                task=kwargs["task"],
                model=model,
                quality_tier=kwargs["quality_tier"],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                latency_ms=kwargs.get("latency_ms", 0),
                status=kwargs.get("status", "success"),
                error_message=kwargs.get("error_message"),
            )
            session.add(event)
            await session.commit()
    except Exception as e:
        log.error("cost_meter_failed", error=str(e), request_id=kwargs.get("request_id"))


async def check_quota(tenant_id: str, monthly_quota_usd: Decimal) -> bool:
    """Return False if tenant has exceeded their monthly quota (quota > 0)."""
    if not monthly_quota_usd or float(monthly_quota_usd) <= 0:
        return True  # unlimited

    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT COALESCE(SUM(cost_usd), 0)
                FROM cost_events
                WHERE tenant_id = :tenant_id
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                  AND status = 'success'
            """),
            {"tenant_id": uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id},
        )
        total = result.scalar() or 0

    return float(total) < float(monthly_quota_usd)


@router.get("/usage/{tenant_id}")
async def get_usage(tenant_id: str):
    """Return current month cost summary for a tenant."""
    async with get_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    COUNT(*) AS total_calls,
                    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                    COALESCE(SUM(cost_usd), 0) AS total_cost_usd
                FROM cost_events
                WHERE tenant_id = :tenant_id
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                  AND status = 'success'
            """),
            {"tenant_id": uuid.UUID(tenant_id)},
        )
        row = result.mappings().one_or_none()
    return dict(row) if row else {}
