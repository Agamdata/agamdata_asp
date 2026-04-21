"""
F-03-03 / PAP-ASP-REQ-ASP-03 v3.0 — assess_test_quality AC Suite

Structure per the ASP-F0303-assess-test-quality-DRAFT §4 skeleton:
  S-1 Handler dispatch + payload validation   (4 ACs)
  S-2 Prompt resolution + reach               (2 ACs)
  S-3 Output shape + bounds                   (5 ACs)
  S-4 Capabilities + schema endpoint          (2 ACs)
  Cross-cutting regression                    (2 ACs)
                                              ==
                                              15 ACs

Runtime approach: FastAPI TestClient (in-process) via the
`authed_client` fixture from conftest.py. Mocks at
`app.services.generation.*` take effect because the test + the
handler run in the same Python process. Live httpx against the
Docker ai-service would not work for mocked LLM calls (different
process).

Stop-on-first-failure: pytest -x (invoked by runner).
Governance reference: ASP-OUT-068/070 build authorisation.
"""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.generation_schemas import (
    TestQualityAssessmentPayload,
    TestQualityAssessmentResult,
    StepContext,
)
from app.services.generation import (
    VALID_TASKS, TASK_OUTPUT_SCHEMAS, TASK_PAYLOAD_VALIDATORS, TASK_MAX_TOKENS,
)
from app.api.capabilities import TASK_SCHEMA_MODELS, SERVICE_CAPABILITIES


# ---------------------------------------------------------------------------
# Anthropic response builder
# ---------------------------------------------------------------------------

def _mock_anth_response(result_dict: dict = None,
                        stop_reason: str = "end_turn"):
    """Anthropic response mimic returning an assess_test_quality JSON."""
    result_dict = result_dict if result_dict is not None else {
        "step_count_adequacy":       0.85,
        "precondition_completeness": 0.75,
        "assertion_coverage":        0.70,
        "edge_case_presence":        0.40,
        "overall_quality_score":     0.68,
        "suggestions": [
            "Add an edge case for max-length name input",
            "Verify permission variation: viewer role cannot create lead",
        ],
    }
    resp = MagicMock()
    block = MagicMock()
    block.text = json.dumps(result_dict)
    resp.content = [block]
    resp.usage = MagicMock(input_tokens=140, output_tokens=110)
    resp.stop_reason = stop_reason
    return resp


# ---------------------------------------------------------------------------
# Prompt-registry autouse fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_f0303_prompt_registry():
    """Stub get_prompt for assess_test_quality + permissive fallback
    for regression probes."""
    from app.registry.prompt_registry import PromptTemplateDTO

    assess_tpl = PromptTemplateDTO(
        id=str(uuid.uuid4()), service_type="generation",
        task="assess_test_quality", caller_module="*", maturity_level="*",
        version=1,
        system_prompt="system for assess_test_quality",
        user_prompt_template=(
            "Screen: {screen_key} / Module: {module_key} "
            "Cat: {category} P: {priority} "
            "Title: {title} Obj: {objective} "
            "Steps: {steps} Preconds: {preconditions} "
            "Expected: {expected_result}"
        ),
    )

    async def _get_prompt(service_type, task, caller_module, maturity_level):
        if (service_type, task) == ("generation", "assess_test_quality"):
            return assess_tpl
        return PromptTemplateDTO(
            id=str(uuid.uuid4()), service_type=service_type, task=task,
            caller_module=caller_module or "*", maturity_level="*",
            version=1,
            system_prompt="fallback system",
            user_prompt_template="{text}",
        )

    async def _get_prompt_variant(service_type, task, caller_module,
                                   maturity_level, ab_variant):
        return await _get_prompt(service_type, task, caller_module,
                                 maturity_level)

    with patch("app.registry.prompt_registry.get_prompt",
               side_effect=_get_prompt), \
         patch("app.registry.prompt_registry.get_prompt_variant",
               side_effect=_get_prompt_variant):
        yield


@pytest.fixture
def valid_payload() -> dict:
    return {
        "screen_key":      "lead_detail",
        "module_key":      "leads",
        "title":           "Create lead — happy path",
        "objective":       "Verify lead creation with required fields succeeds",
        "category":        "Functional",
        "priority":        "High",
        "steps": [
            {"step_no": 1, "action": "navigate /leads/new",
             "expected": "lead form visible"},
            {"step_no": 2, "action": "fill name='Acme'",
             "expected": "name populated"},
            {"step_no": 3, "action": "click Save",
             "expected": "lead persisted"},
        ],
        "preconditions":   ["user authenticated", "leads module enabled"],
        "expected_result": "Lead appears in leads list with name='Acme'",
    }


def _invoke(client, payload: dict):
    body = {
        "service_type":   "generation",
        "task":           "assess_test_quality",
        "caller_module":  "test_suite",
        "tenant_id":      "test_tenant",
        "payload":        payload,
        "user_context":   {"user_id": "u", "role": "tester",
                           "maturity_level": "L2"},
    }
    return client.post("/api/v1/ai/invoke", json=body)


# ===========================================================================
# Block S-1 — Handler dispatch + payload validation (4 ACs)
# ===========================================================================

class TestS1Dispatch:

    def test_ac_f303_s1_01_task_in_valid_tasks(self):
        assert "assess_test_quality" in VALID_TASKS

    def test_ac_f303_s1_02_output_schema_registered(self):
        assert TASK_OUTPUT_SCHEMAS.get("assess_test_quality") is TestQualityAssessmentResult

    def test_ac_f303_s1_03_payload_validator_registered(self):
        assert TASK_PAYLOAD_VALIDATORS.get("assess_test_quality") is TestQualityAssessmentPayload

    def test_ac_f303_s1_04_missing_steps_raises_422(
        self, authed_client, mock_anthropic, valid_payload
    ):
        """Payload without `steps` key → 422 at endpoint."""
        mock_anthropic.messages.create = AsyncMock(return_value=_mock_anth_response())
        bad = dict(valid_payload)
        bad.pop("steps")
        r = _invoke(authed_client, bad)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:200]}"


# ===========================================================================
# Block S-2 — Prompt resolution + reach (2 ACs)
# ===========================================================================

class TestS2PromptReach:

    def test_ac_f303_s2_01_max_tokens_set(self):
        assert TASK_MAX_TOKENS.get("assess_test_quality") == 2048

    def test_ac_f303_s2_02_wildcard_row_reachable(self):
        """Governed wildcard row at (generation, assess_test_quality,
        '*', '*', v1) must be present in prompt_templates."""
        async def _probe():
            from app.config import settings
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine
            engine = create_async_engine(settings.DATABASE_URL,
                                         pool_pre_ping=False)
            try:
                async with engine.connect() as conn:
                    row = (
                        await conn.execute(
                            text("""
                                SELECT COUNT(*) FROM prompt_templates
                                WHERE service_type = 'generation'
                                  AND task = 'assess_test_quality'
                                  AND caller_module = '*'
                                  AND maturity_level = '*'
                                  AND version = 1
                                  AND is_active = TRUE
                            """)
                        )
                    ).scalar()
            finally:
                await engine.dispose()
            return row
        assert asyncio.run(_probe()) == 1, \
            "wildcard prompt row missing — migration 0030 not applied"


# ===========================================================================
# Block S-3 — Output shape + bounds (5 ACs)
# ===========================================================================

class TestS3OutputShape:

    def test_ac_f303_s3_01_valid_payload_200(
        self, authed_client, mock_anthropic, valid_payload
    ):
        mock_anthropic.messages.create = AsyncMock(return_value=_mock_anth_response())
        r = _invoke(authed_client, valid_payload)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        assert "result" in r.json()

    def test_ac_f303_s3_02_all_five_dimension_scores(
        self, authed_client, mock_anthropic, valid_payload
    ):
        mock_anthropic.messages.create = AsyncMock(return_value=_mock_anth_response())
        r = _invoke(authed_client, valid_payload)
        assert r.status_code == 200
        result = r.json()["result"]
        for key in ("step_count_adequacy", "precondition_completeness",
                    "assertion_coverage", "edge_case_presence",
                    "overall_quality_score"):
            assert key in result, f"missing {key}"
            assert isinstance(result[key], (int, float)), \
                f"{key} not numeric: {result[key]!r}"

    def test_ac_f303_s3_03_scores_in_bounds_0_to_1(
        self, authed_client, mock_anthropic, valid_payload
    ):
        mock_anthropic.messages.create = AsyncMock(return_value=_mock_anth_response())
        r = _invoke(authed_client, valid_payload)
        assert r.status_code == 200
        result = r.json()["result"]
        for key in ("step_count_adequacy", "precondition_completeness",
                    "assertion_coverage", "edge_case_presence",
                    "overall_quality_score"):
            v = result[key]
            assert 0.0 <= v <= 1.0, f"{key}={v} out of [0.0, 1.0]"

    def test_ac_f303_s3_04_suggestions_list_of_strings(
        self, authed_client, mock_anthropic, valid_payload
    ):
        mock_anthropic.messages.create = AsyncMock(return_value=_mock_anth_response())
        r = _invoke(authed_client, valid_payload)
        assert r.status_code == 200
        sugg = r.json()["result"].get("suggestions", [])
        assert isinstance(sugg, list)
        assert all(isinstance(s, str) for s in sugg)

    def test_ac_f303_s3_05_empty_suggestions_accepted(
        self, authed_client, mock_anthropic, valid_payload
    ):
        mock_anthropic.messages.create = AsyncMock(return_value=_mock_anth_response({
            "step_count_adequacy":       1.0,
            "precondition_completeness": 1.0,
            "assertion_coverage":        1.0,
            "edge_case_presence":        1.0,
            "overall_quality_score":     1.0,
            "suggestions":               [],
        }))
        r = _invoke(authed_client, valid_payload)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        assert r.json()["result"]["suggestions"] == []


# ===========================================================================
# Block S-4 — Capabilities + schema endpoint (2 ACs)
# ===========================================================================

class TestS4Capabilities:

    def test_ac_f303_s4_01_in_service_capabilities(self):
        assert "assess_test_quality" in SERVICE_CAPABILITIES["generation"]

    def test_ac_f303_s4_02_schema_endpoint_returns_json_schema(
        self, authed_client
    ):
        r = authed_client.get(
            "/api/v1/ai/schemas/generation/assess_test_quality"
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        schema = r.json()
        assert "properties" in schema or "$schema" in schema or "type" in schema
        props = schema.get("properties", {})
        if props:
            assert "expected_result" in props, \
                "expected_result missing from JSON schema"


# ===========================================================================
# Block cross-cutting — regression (2 ACs)
# ===========================================================================

class TestCrossCutting:

    def test_ac_f303_cc_01_f0302_trio_unaffected(self):
        for t in ("draft_steps", "suggest_preconditions",
                  "propose_edge_cases"):
            assert t in VALID_TASKS
            assert t in TASK_OUTPUT_SCHEMAS
            assert t in TASK_PAYLOAD_VALIDATORS

    def test_ac_f303_cc_02_existing_generation_tasks_unaffected(self):
        for t in ("generate_test_cases", "generate_playwright_script",
                  "refactor_script_locators"):
            assert t in VALID_TASKS
            assert t in TASK_OUTPUT_SCHEMAS
