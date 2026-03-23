"""
Phase 3 acceptance tests — tests/test_cost_meter.py
"""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.cost.meter import calculate_cost, check_quota, emit_cost_event


# Test: calculate_cost returns non-negative float
def test_calculate_cost_haiku():
    cost = calculate_cost("claude-haiku-4-5-20251001", 1000, 500)
    assert cost >= 0
    # 1000 * 0.80 / 1_000_000 + 500 * 4.00 / 1_000_000 = 0.0008 + 0.002 = 0.0028
    assert abs(cost - 0.0028) < 1e-6


def test_calculate_cost_sonnet():
    cost = calculate_cost("claude-sonnet-4-6", 1000, 500)
    assert cost >= 0
    # 1000 * 3.00 / 1_000_000 + 500 * 15.00 / 1_000_000 = 0.003 + 0.0075 = 0.0105
    assert abs(cost - 0.0105) < 1e-6


def test_calculate_cost_unknown_model():
    cost = calculate_cost("unknown-model", 1000, 500)
    assert cost >= 0


# Test: emit_cost_event does not raise on DB failure (MUST NOT raise)
@pytest.mark.asyncio
async def test_emit_cost_event_does_not_raise_on_failure():
    with patch("app.cost.meter.get_session") as mock_session_ctx:
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock(side_effect=Exception("DB down"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_ctx.return_value = mock_session

        # Should NOT raise
        await emit_cost_event(
            request_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            caller_module="crm",
            service_type="nlp",
            task="nl_to_sql",
            model="claude-haiku-4-5-20251001",
            quality_tier="standard",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
        )


# Test: check_quota returns True when under quota
@pytest.mark.asyncio
async def test_check_quota_under_limit():
    with patch("app.cost.meter.get_session") as mock_session_ctx:
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("10.00")  # $10 spent of $50 quota
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_ctx.return_value = mock_session

        result = await check_quota(str(uuid.uuid4()), Decimal("50.00"))
        assert result is True


# Test: check_quota returns False when over quota
@pytest.mark.asyncio
async def test_check_quota_exceeded():
    with patch("app.cost.meter.get_session") as mock_session_ctx:
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("55.00")  # $55 spent, over $50 quota
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_ctx.return_value = mock_session

        result = await check_quota(str(uuid.uuid4()), Decimal("50.00"))
        assert result is False


# Test: check_quota returns True when quota is 0 (unlimited)
@pytest.mark.asyncio
async def test_check_quota_unlimited():
    result = await check_quota(str(uuid.uuid4()), Decimal("0"))
    assert result is True
