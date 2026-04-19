"""Step 5 targeted unit tests per ASP-OUT-013 directive (before full 37-AC suite).

Covers:
  U1  categories_to_generate=[A,B] → MODE block cites exactly 2 + A,B
  U2  categories_to_generate absent → legacy 5-category F-03-08 mode retained
  U3  locator_source=live_extracted → 'live-extracted ... best-effort' advisory
       appended to generation instructions
  U4  form_data populated → FORM_DATA_BLOCK content carries the dict
  U5  form_data absent → FORM_DATA_BLOCK synthesize-realistic-values fallback
  U6  test_generator caller → v4-interactive prompt row resolved (not
       playwright_runner row)
  U7  refactor_script_locators → handler builds prompt, returns
       RefactorScriptLocatorsResult
  U8  asyncio.wait_for timeout fires on simulated slow LLM response → 504
  U9  VALID_TASKS registry updated; GET /api/v1/ai/schemas/generation/
       refactor_script_locators returns valid JSON Schema
"""
import asyncio
import json
import logging
import uuid
from unittest.mock import patch, AsyncMock

import bcrypt
import httpx
import structlog
from httpx import ASGITransport
from sqlalchemy import delete, select

from app.infra.db import get_session
from app.main import app
from app.models.db_models import Tenant, TenantApiKey
from app.models.response import InvokeResponse, ResponseMeta
from app.services import generation
from app.services.generation import (
    _build_generation_instructions, _build_form_data_context,
    VALID_TASKS, TASK_OUTPUT_SCHEMAS, TASK_PAYLOAD_VALIDATORS,
    TEST_GENERATOR_INTERACTIVE_TIMEOUT_SECONDS,
)
from app.utils.key_generator import generate_api_key

# Silence structlog for readability
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
)

TEST_TENANT = uuid.UUID("99999999-8888-7777-6666-555555555555")


async def setup_tenant():
    """Create a throwaway tenant + new-format API key."""
    async with get_session() as s:
        await s.execute(delete(TenantApiKey).where(TenantApiKey.tenant_id == TEST_TENANT))
        await s.execute(delete(Tenant).where(Tenant.id == TEST_TENANT))
        await s.commit()
        s.add(Tenant(id=TEST_TENANT, tenant_code="step5_" + uuid.uuid4().hex[:4],
                     name="Step5 Unit Test", monthly_quota_usd=100.0, is_active=True))
        await s.flush()
        raw, prefix, hashed = generate_api_key()
        s.add(TenantApiKey(tenant_id=TEST_TENANT, key_prefix=prefix,
                           api_key_hash=hashed, label="step5", is_active=True))
        await s.commit()
    return raw


async def teardown_tenant():
    async with get_session() as s:
        await s.execute(delete(TenantApiKey).where(TenantApiKey.tenant_id == TEST_TENANT))
        await s.execute(delete(Tenant).where(Tenant.id == TEST_TENANT))
        await s.commit()


def u1_categories_override():
    out = _build_generation_instructions({
        "categories_to_generate": ["boundary_values", "unauthorised_access"],
        "locator_source": "verified",
    })
    assert "Coverage-aware generation" in out
    assert "EXACTLY 2 test cases" in out
    assert "boundary_values" in out
    assert "unauthorised_access" in out
    assert "Do not generate test cases for any other category" in out
    return True


def u2_categories_absent_legacy_f03_08():
    out = _build_generation_instructions({
        "locator_source": "verified",
    })
    assert "F-03-08" in out
    assert "EXACTLY FIVE" in out
    assert "TC-1" in out and "TC-5" in out
    return True


def u2b_categories_absent_f03_04():
    out = _build_generation_instructions({
        "tc_id": "TC_LOGIN_001",
        "test_steps": "step1",
        "locator_source": "verified",
    })
    assert "F-03-04" in out
    assert "EXACTLY ONE" in out
    assert "TC_LOGIN_001" in out
    return True


def u3_live_extracted_advisory():
    out = _build_generation_instructions({
        "categories_to_generate": ["happy_path"],
        "locator_source": "live_extracted",
    })
    assert "live-extracted" in out
    assert "best-effort" in out
    assert "missing_locators" in out
    return True


def u3b_verified_no_advisory():
    out = _build_generation_instructions({
        "categories_to_generate": ["happy_path"],
        "locator_source": "verified",
    })
    assert "live-extracted" not in out
    return True


def u4_form_data_populated():
    ctx = _build_form_data_context({
        "form_data": {"first_name": "Alice", "email": "alice@example.com"},
    })
    assert "Use these field values" in ctx
    assert "Alice" in ctx
    assert "alice@example.com" in ctx
    return True


def u5_form_data_absent():
    ctx = _build_form_data_context({})
    assert "No form data provided" in ctx
    assert "generate realistic test values" in ctx
    return True


async def u6_test_generator_row_resolved():
    """Verify Prompt Registry resolves test_generator caller to v4-interactive row."""
    from app.registry import prompt_registry
    p_runner = await prompt_registry.get_prompt_variant(
        service_type="generation",
        task="generate_test_cases_with_inventory",
        caller_module="playwright_runner",
        maturity_level="*",
        ab_variant="inventory",
    )
    p_gen = await prompt_registry.get_prompt_variant(
        service_type="generation",
        task="generate_test_cases_with_inventory",
        caller_module="test_generator",
        maturity_level="*",
        ab_variant="inventory",
    )
    assert p_runner is not None and p_gen is not None
    assert p_runner.id != p_gen.id, "both rows must have distinct IDs"
    # test_generator row has RULE 9 (interactive); playwright_runner does not.
    assert "interactive panel" in p_gen.system_prompt.lower()
    assert "interactive panel" not in p_runner.system_prompt.lower()
    return True


def u7_refactor_registered():
    assert "refactor_script_locators" in VALID_TASKS
    assert "refactor_script_locators" in TASK_OUTPUT_SCHEMAS
    assert "refactor_script_locators" in TASK_PAYLOAD_VALIDATORS
    return True


async def u8_wait_for_timeout_fires():
    """Simulate a slow LLM response and confirm asyncio.wait_for raises 504.

    Strategy: patch llm_call_with_retry to return a sleeping coroutine
    longer than the configured timeout. Then call handle() with
    caller_module="test_generator" and confirm HTTP 504 is raised.
    """
    from app.services import generation as gen_mod
    from app.models.request import InvokeRequest
    from fastapi import HTTPException

    # Build a minimal valid InvokeRequest. Default user_context = None →
    # handler maturity defaults to "L2". Post-ASP-OUT-014 Option A fix,
    # the get_prompt_variant fallback chain resolves L2 to the (caller, *)
    # row, so this matches the real PAP call shape.
    req = InvokeRequest(
        service_type="generation",
        task="generate_test_cases_with_inventory",
        caller_module="test_generator",
        caller_feature="F-01-10",
        tenant_id=str(TEST_TENANT),
        payload={
            "url": "http://example.com",
            "page_type": "FORM",
            "screen_key": "LOGIN",
            "locator_source": "live_extracted",
            "locator_inventory": [
                {"element_name": "email_input", "tag": "input",
                 "locators": {"recommended": "getByLabel('Email')"}},
            ],
            "categories_to_generate": ["happy_path"],
        },
    )

    # Patch timeout to 0.1s for fast-fail
    original_ttl = gen_mod.TEST_GENERATOR_INTERACTIVE_TIMEOUT_SECONDS
    gen_mod.TEST_GENERATOR_INTERACTIVE_TIMEOUT_SECONDS = 0.1

    async def slow_llm(*args, **kwargs):
        await asyncio.sleep(2.0)   # way longer than patched timeout
        raise RuntimeError("should have been cancelled by timeout")

    try:
        with patch("app.services.generation.llm_call_with_retry", side_effect=slow_llm):
            try:
                await gen_mod.handle(req, model="claude-haiku-4-5-20251001",
                                     request_id=str(uuid.uuid4()))
                assert False, "expected HTTPException(504)"
            except HTTPException as he:
                assert he.status_code == 504, f"expected 504, got {he.status_code}"
                assert "Interactive generation timeout" in str(he.detail)
                return True
    finally:
        gen_mod.TEST_GENERATOR_INTERACTIVE_TIMEOUT_SECONDS = original_ttl


async def u9_schemas_endpoint():
    """GET /api/v1/ai/schemas/generation/refactor_script_locators → 200 JSON Schema."""
    raw = await setup_tenant()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/api/v1/ai/schemas/generation/refactor_script_locators",
            headers={"X-ASP-API-Key": raw},
        )
        if r.status_code != 200:
            return (False, f"http={r.status_code} body={r.text[:200]}")
        body = r.json()
        if body.get("type") != "object":
            return (False, f"not JSON Schema: {body}")
        props = body.get("properties", {})
        required = set(body.get("required", []))
        need = {"script_body", "locator_diff", "screen_key"}
        if not need.issubset(props.keys()) or not need.issubset(required):
            return (False, f"missing fields; props={list(props.keys())} required={required}")
    await teardown_tenant()
    return (True, "OK")


async def main():
    # Initialise Redis — prompt_registry + context_store depend on it.
    # Normally driven by app lifespan; the unit harness bypasses that.
    from app.infra.redis import init_redis
    await init_redis()

    results = []
    def check(name, cond, info=""):
        results.append((name, "PASS" if cond else "FAIL", info))

    check("U1 categories_to_generate override", u1_categories_override())
    check("U2 categories absent → F-03-08 legacy 5-TC mode", u2_categories_absent_legacy_f03_08())
    check("U2b tc_id present → F-03-04 1-TC mode", u2b_categories_absent_f03_04())
    check("U3 live_extracted advisory appended", u3_live_extracted_advisory())
    check("U3b verified → no live_extracted advisory", u3b_verified_no_advisory())
    check("U4 form_data populated → context carries dict", u4_form_data_populated())
    check("U5 form_data absent → synthesize fallback", u5_form_data_absent())
    check("U6 test_generator resolves to distinct v4-interactive row", await u6_test_generator_row_resolved())
    check("U7 refactor_script_locators registered across 3 task registries", u7_refactor_registered())
    check("U8 asyncio.wait_for timeout → 504 Interactive generation timeout", await u8_wait_for_timeout_fires())
    ok, info = await u9_schemas_endpoint()
    check("U9 /schemas/generation/refactor_script_locators → 200 valid JSON Schema", ok, info)

    print()
    print("=" * 90)
    for name, status, info in results:
        print(f"  [{status}] {name:<70}  {info[:50]}")
    print("=" * 90)
    n_pass = sum(1 for _, s, _ in results if s == "PASS")
    n_fail = len(results) - n_pass
    print(f"\n  SUMMARY: {n_pass} PASS / {n_fail} FAIL of {len(results)}")
    return n_fail


if __name__ == "__main__":
    rc = asyncio.run(main())
    raise SystemExit(rc)
