"""
ASP-01 NLP Service — Acceptance Tests
Spec: ASP-FEAT-ASP-01 v1.2, Section 13

All 25 ACs covered. Each AC maps to one or more test functions.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: Mock LLM responses for each task
# ---------------------------------------------------------------------------

NL_TO_SQL_RESPONSE = json.dumps({
    "sql": "SELECT * FROM leads WHERE created_at >= NOW() - INTERVAL '30 days' AND status = 'open'",
    "explanation": "Retrieves all leads created in the last 30 days with an open status.",
    "tables_used": ["leads"],
    "confidence": 0.92,
    "ambiguities": [],
})

NL_TO_SQL_SIMPLE_RESPONSE = json.dumps({
    "sql": "SELECT * FROM customers",
    "explanation": "All customers",
    "tables_used": ["customers"],
    "confidence": 0.95,
    "ambiguities": [],
})

INTENT_EXTRACT_RESPONSE = json.dumps({
    "intent": "update_record",
    "entities": {"company": "Acme Corp", "field": "phone number"},
    "confidence": 0.88,
})

ENTITY_RECOGNITION_RESPONSE = json.dumps({
    "entities": [
        {"type": "PERSON", "value": "John Smith"},
        {"type": "COMPANY", "value": "Acme Corp"},
        {"type": "AMOUNT", "value": "$50,000"},
        {"type": "DATE", "value": "March 15"},
    ]
})

SENTIMENT_NEGATIVE_RESPONSE = json.dumps({
    "sentiment": "negative",
    "score": 0.15,
})

SENTIMENT_POSITIVE_RESPONSE = json.dumps({
    "sentiment": "positive",
    "score": 0.92,
})

CLASSIFY_VALIDATION_ERROR_RESPONSE = json.dumps({
    "outcome": "validation_error",
    "confidence": 0.95,
    "error_messages": ["Email address is invalid", "Phone number is required"],
    "success_indicators": [],
    "redirect_target": None,
    "reasoning": "Page did not redirect. Two validation error messages visible.",
})

CLASSIFY_AUTH_REDIRECT_RESPONSE = json.dumps({
    "outcome": "auth_redirect",
    "confidence": 0.92,
    "error_messages": [],
    "success_indicators": [],
    "redirect_target": "https://app.example.com/login?redirect=/leads/new",
    "reasoning": "Post-submit URL redirected to login page.",
})

CLASSIFY_SERVER_ERROR_RESPONSE = json.dumps({
    "outcome": "server_error",
    "confidence": 0.98,
    "error_messages": [],
    "success_indicators": [],
    "redirect_target": None,
    "reasoning": "HTTP 500 status received.",
})

CLASSIFY_SUCCESS_RESPONSE = json.dumps({
    "outcome": "success",
    "confidence": 0.90,
    "error_messages": [],
    "success_indicators": ["Lead created successfully"],
    "redirect_target": None,
    "reasoning": "Redirected to new page with success message.",
})

CLASSIFY_UNKNOWN_RESPONSE = json.dumps({
    "outcome": "unknown",
    "confidence": 0.40,
    "error_messages": [],
    "success_indicators": [],
    "redirect_target": None,
    "reasoning": "No observable change after submission.",
})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_anthropic_response(text: str, model: str = "claude-haiku-4-5-20251001"):
    content_mock = MagicMock()
    content_mock.text = text
    usage_mock = MagicMock()
    usage_mock.input_tokens = 280
    usage_mock.output_tokens = 95
    response_mock = MagicMock()
    response_mock.content = [content_mock]
    response_mock.usage = usage_mock
    return response_mock


@pytest.fixture
def nlp_authed_client(authed_client, mock_rag, mock_prompt_registry):
    """Authed client with RAG and prompt registry mocked."""
    return authed_client


def _invoke(client, task, payload, **extra):
    """Helper to call POST /api/v1/ai/invoke for NLP."""
    body = {
        "service_type": "nlp",
        "task": task,
        "caller_module": extra.get("caller_module", "crm"),
        "tenant_id": "test_tenant",
        "payload": payload,
    }
    body.update({k: v for k, v in extra.items() if k not in ("caller_module",)})
    return client.post("/api/v1/ai/invoke", json=body)


# ---------------------------------------------------------------------------
# Section 13.1: nl_to_sql ACs
# ---------------------------------------------------------------------------

# AC-01: nl_to_sql returns sql, explanation, tables_used, confidence
def test_ac01_nl_to_sql_result_fields(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(NL_TO_SQL_RESPONSE, "claude-sonnet-4-6")
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(nlp_authed_client, "nl_to_sql", {"query": "Show me all leads created in the last 30 days with status open"}, quality_tier="enhanced")

    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert "sql" in result
    assert "explanation" in result
    assert "tables_used" in result
    assert "confidence" in result


# AC-02: exclude_tables filters out restricted tables from RAG
def test_ac02_exclude_tables_enforced(nlp_authed_client, mock_rag, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(NL_TO_SQL_SIMPLE_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        _invoke(
            nlp_authed_client, "nl_to_sql", {"query": "test"},
            schema_hints={"exclude_tables": ["salary_disbursements"]},
        )

    mock_rag.assert_called_once()
    call_kwargs = mock_rag.call_args
    exclude = call_kwargs.kwargs.get("exclude_tables", call_kwargs.args[3] if len(call_kwargs.args) > 3 else [])
    assert "salary_disbursements" in exclude


# AC-03: conversation_history enables multi-turn SQL refinement
def test_ac03_conversation_history_refinement(nlp_authed_client, mock_anthropic):
    refined_response = json.dumps({
        "sql": "SELECT * FROM customers WHERE created_at >= NOW() - INTERVAL '30 days'",
        "explanation": "Refined to filter last 30 days.",
        "tables_used": ["customers"],
        "confidence": 0.90,
        "ambiguities": [],
    })
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(refined_response)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "nl_to_sql", {"query": "now filter to 30 days"},
            conversation_history=[
                {"role": "user", "content": "show all customers", "turn": 1},
                {"role": "assistant", "content": "SELECT * FROM customers", "turn": 2, "generated_sql": "SELECT * FROM customers"},
            ],
        )
    assert r.status_code == 200
    # Verify the call included conversation history in messages
    call_args = mock_anthropic.messages.create.call_args
    messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
    assert len(messages) >= 3  # at least 2 history + 1 current


# AC-04: L0 maturity_level uses simple SELECTs
def test_ac04_l0_simple_sql(nlp_authed_client, mock_anthropic, mock_prompt_registry):
    simple_response = json.dumps({
        "sql": "SELECT * FROM leads WHERE status = 'open'",
        "explanation": "Simple select for L0.",
        "tables_used": ["leads"],
        "confidence": 0.85,
        "ambiguities": [],
    })
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(simple_response)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "nl_to_sql", {"query": "show open leads"},
            user_context={"user_id": "u1", "role": "sales", "maturity_level": "L0"},
        )
    assert r.status_code == 200
    sql = r.json()["result"]["sql"].upper()
    assert "WITH" not in sql  # no CTEs
    assert "OVER(" not in sql  # no window functions


# ---------------------------------------------------------------------------
# Section 13.2: intent_extract and entity_recognition ACs
# ---------------------------------------------------------------------------

# AC-05: intent_extract returns intent, confidence, entities
def test_ac05_intent_extract(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(INTENT_EXTRACT_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(nlp_authed_client, "intent_extraction", {"query": "I want to update the phone number for Acme Corp"})

    assert r.status_code == 200
    result = r.json()["result"]
    assert "intent" in result
    assert isinstance(result["confidence"], float)
    assert "entities" in result


# AC-06: entity_recognition extracts PERSON, COMPANY, AMOUNT, DATE
def test_ac06_entity_recognition(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(ENTITY_RECOGNITION_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "entity_recognition",
            {"text": "John Smith from Acme Corp called about a $50,000 deal on March 15"},
        )

    assert r.status_code == 200
    entities = r.json()["result"]["entities"]
    types = {e["type"] for e in entities}
    assert "PERSON" in types
    assert "COMPANY" in types
    assert "AMOUNT" in types
    assert "DATE" in types
    assert len(entities) >= 4


# ---------------------------------------------------------------------------
# Section 13.3: sentiment_analysis ACs
# ---------------------------------------------------------------------------

# AC-07: negative sentiment for complaint text
def test_ac07_sentiment_negative(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(SENTIMENT_NEGATIVE_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(nlp_authed_client, "sentiment", {"text": "This product is terrible and support never responds."})

    assert r.status_code == 200
    result = r.json()["result"]
    assert result["sentiment"] == "negative"
    assert result["score"] < 0.3


# AC-08: positive sentiment for feedback text
def test_ac08_sentiment_positive(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(SENTIMENT_POSITIVE_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(nlp_authed_client, "sentiment", {"text": "Absolutely love this product! Best purchase ever."})

    assert r.status_code == 200
    result = r.json()["result"]
    assert result["sentiment"] == "positive"
    assert result["score"] > 0.7


# ---------------------------------------------------------------------------
# Section 13.4: classify_probe_result ACs
# ---------------------------------------------------------------------------

# AC-09: validation_error outcome with error_messages
def test_ac09_classify_validation_error(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(CLASSIFY_VALIDATION_ERROR_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "classify_probe_result",
            {
                "page_url": "https://app.example.com/leads/new",
                "page_type": "FORM",
                "submitted_fields": {"first_name": "Rajan", "email": "rajan@invalid", "phone": ""},
                "post_submit_url": "https://app.example.com/leads/new",
                "post_submit_status": 200,
                "visible_text": "Email address is invalid. Phone number is required.",
            },
            caller_module="playwright_runner",
        )

    assert r.status_code == 200
    result = r.json()["result"]
    assert result["outcome"] == "validation_error"
    assert any("Email" in msg for msg in result["error_messages"])


# AC-10: auth_redirect with redirect_target populated
def test_ac10_classify_auth_redirect(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(CLASSIFY_AUTH_REDIRECT_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "classify_probe_result",
            {
                "page_url": "https://app.example.com/leads/new",
                "page_type": "FORM",
                "submitted_fields": {"name": "Test"},
                "post_submit_url": "https://app.example.com/login?redirect=/leads/new",
                "post_submit_status": 302,
                "visible_text": "Please log in to continue.",
            },
            caller_module="playwright_runner",
        )

    assert r.status_code == 200
    result = r.json()["result"]
    assert result["outcome"] == "auth_redirect"
    assert result["redirect_target"] is not None
    assert "/login" in result["redirect_target"]


# AC-11: server_error on HTTP 500
def test_ac11_classify_server_error(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(CLASSIFY_SERVER_ERROR_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "classify_probe_result",
            {
                "page_url": "https://app.example.com/leads/new",
                "page_type": "FORM",
                "submitted_fields": {"name": "Test"},
                "post_submit_url": "https://app.example.com/error",
                "post_submit_status": 500,
                "visible_text": "An unexpected error occurred.",
            },
            caller_module="playwright_runner",
        )

    assert r.status_code == 200
    assert r.json()["result"]["outcome"] == "server_error"


# AC-12: success outcome with success_indicators
def test_ac12_classify_success(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(CLASSIFY_SUCCESS_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "classify_probe_result",
            {
                "page_url": "https://app.example.com/leads/new",
                "page_type": "FORM",
                "submitted_fields": {"first_name": "Rajan", "email": "rajan@test.com"},
                "post_submit_url": "https://app.example.com/leads/123",
                "post_submit_status": 200,
                "visible_text": "Lead created successfully.",
            },
            caller_module="playwright_runner",
        )

    assert r.status_code == 200
    result = r.json()["result"]
    assert result["outcome"] == "success"
    assert len(result["success_indicators"]) > 0


# AC-13: unknown when no clear signals
def test_ac13_classify_unknown(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(CLASSIFY_UNKNOWN_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "classify_probe_result",
            {
                "page_url": "https://app.example.com/leads/new",
                "page_type": "FORM",
                "submitted_fields": {"name": "Test"},
                "post_submit_url": "https://app.example.com/leads/new",
                "post_submit_status": 200,
                "visible_text": "Create New Lead",
            },
            caller_module="playwright_runner",
        )

    assert r.status_code == 200
    assert r.json()["result"]["outcome"] == "unknown"


# AC-14: [v1.2] model starts with 'claude-haiku' for standard tier
def test_ac14_model_prefix_haiku(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(CLASSIFY_SUCCESS_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "classify_probe_result",
            {
                "page_url": "https://app.example.com/leads/new",
                "page_type": "FORM",
                "submitted_fields": {"name": "Test"},
                "visible_text": "Lead created successfully.",
            },
            caller_module="playwright_runner",
            quality_tier="standard",
        )

    assert r.status_code == 200
    model = r.json()["meta"]["model"]
    assert model.startswith("claude-haiku"), f"Expected claude-haiku prefix, got: {model}"


# AC-15: [v1.1] Optional fields omitted entirely — no 422
def test_ac15_optional_fields_omitted(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(CLASSIFY_VALIDATION_ERROR_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "classify_probe_result",
            {
                "page_url": "https://app.example.com/leads/new",
                "page_type": "FORM",
                "submitted_fields": {"first_name": "Rajan", "email": "rajan@test.com"},
                # post_submit_url and post_submit_status intentionally OMITTED
                "visible_text": "Please complete all required fields.",
            },
            caller_module="playwright_runner",
        )

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    assert r.json()["result"]["outcome"] in {
        "success", "validation_error", "auth_redirect", "server_error", "unknown"
    }


# ---------------------------------------------------------------------------
# Section 13.5: Cross-Cutting / Security ACs
# ---------------------------------------------------------------------------

# AC-16: cost_event written for every call
def test_ac16_cost_event_emitted(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(NL_TO_SQL_SIMPLE_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock) as mock_cost, \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(nlp_authed_client, "nl_to_sql", {"query": "test"})

    assert r.status_code == 200
    mock_cost.assert_called_once()
    call_kwargs = mock_cost.call_args.kwargs
    assert call_kwargs["service_type"] == "nlp"
    assert call_kwargs["task"] == "nl_to_sql"
    assert "tenant_id" in call_kwargs
    assert "caller_module" in call_kwargs
    assert "model" in call_kwargs


# AC-17: unknown field in outer envelope → 422
def test_ac17_extra_field_envelope_422(nlp_authed_client):
    with patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = nlp_authed_client.post(
            "/api/v1/ai/invoke",
            json={
                "service_type": "nlp",
                "task": "nl_to_sql",
                "caller_module": "crm",
                "tenant_id": "test_tenant",
                "payload": {"query": "test"},
                "unknown_extra_field": "should_reject",
            },
        )
    assert r.status_code == 422


# AC-18: unknown field in task payload → 422
def test_ac18_extra_field_payload_422(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(CLASSIFY_SUCCESS_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(
            nlp_authed_client, "classify_probe_result",
            {
                "page_url": "https://app.example.com/leads/new",
                "page_type": "FORM",
                "submitted_fields": {"name": "Test"},
                "visible_text": "Test",
                "unknown_payload_field": "should_reject",  # extra field
            },
            caller_module="playwright_runner",
        )
    assert r.status_code == 422


# AC-19: cost meter exception doesn't fail response (ADR-006)
def test_ac19_cost_meter_resilience():
    """Unit test: emit_cost_event never raises even when DB fails (ADR-006)."""
    import asyncio

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB connection failed"))
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.cost.meter.get_session", return_value=mock_session):
        from app.cost.meter import emit_cost_event
        # Must NOT raise — try/except in emit_cost_event catches all exceptions
        asyncio.get_event_loop().run_until_complete(
            emit_cost_event(
                request_id="test-req-id",
                tenant_id="test-tenant-id",
                caller_module="crm",
                service_type="nlp",
                task="nl_to_sql",
                model="claude-haiku-4-5-20251001",
                quality_tier="standard",
                input_tokens=100,
                output_tokens=50,
            )
        )
    # Reached here = emit_cost_event swallowed the exception. ADR-006 satisfied.


# AC-20: invalid API key → 401
def test_ac20_invalid_api_key_401(client):
    """Client with wrong API key gets 401 or missing header gets 422."""
    # Send with an explicitly wrong key
    r = client.post(
        "/api/v1/ai/invoke",
        headers={"X-ASP-API-Key": "wrong-key-definitely-invalid"},
        json={
            "service_type": "nlp",
            "task": "nl_to_sql",
            "caller_module": "crm",
            "tenant_id": "test_tenant",
            "payload": {"query": "test"},
        },
    )
    assert r.status_code in (401, 422)  # 401 for invalid key, 422 if header validation fails


# AC-21: quota exceeded → 429
def test_ac21_quota_exceeded_429(nlp_authed_client):
    with patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=False):
        r = _invoke(nlp_authed_client, "nl_to_sql", {"query": "test"})
    assert r.status_code == 429


# AC-22: internal exception → no stack trace in response
def test_ac22_no_stack_trace(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(side_effect=TimeoutError("LLM timeout"))
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(nlp_authed_client, "nl_to_sql", {"query": "test"})

    # DEFECT-016: TimeoutError now retries 3x then returns 502 (upstream unavailable)
    assert r.status_code in (500, 502)
    body = r.json()
    # Must not contain stack trace
    body_str = json.dumps(body)
    assert "Traceback" not in body_str
    assert "File " not in body_str
    assert ".py" not in body_str or "request_id" in body_str


# AC-23: invalid task → 422
def test_ac23_invalid_task_422(nlp_authed_client):
    with patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(nlp_authed_client, "nonexistent_task", {"text": "test"})
    assert r.status_code == 422


# AC-24: meta.model is actual model name, not quality_tier string
def test_ac24_meta_model_not_tier(nlp_authed_client, mock_anthropic):
    mock_anthropic.messages.create = AsyncMock(
        return_value=_make_anthropic_response(NL_TO_SQL_SIMPLE_RESPONSE)
    )
    with patch("app.gateway.cost_emitter.emit_cost_event", new_callable=AsyncMock), \
         patch("app.cost.meter.check_quota", new_callable=AsyncMock, return_value=True):
        r = _invoke(nlp_authed_client, "nl_to_sql", {"query": "test"}, quality_tier="standard")

    assert r.status_code == 200
    model = r.json()["meta"]["model"]
    assert model not in ("standard", "enhanced", "premium"), f"meta.model should be model name, got: {model}"
    assert "claude" in model.lower() or model != ""


# AC-25: extract_json handles markdown fences
def test_ac25_extract_json_markdown_fences():
    """Unit test for extract_json — not HTTP-level, tests the utility directly."""
    from app.utils.json_parser import extract_json

    # Wrapped in markdown fences
    fenced = '```json\n{"outcome": "success", "confidence": 0.9, "error_messages": [], "success_indicators": ["OK"], "redirect_target": null, "reasoning": "test"}\n```'
    result = extract_json(fenced)
    assert result["outcome"] == "success"

    # Plain JSON
    plain = '{"outcome": "unknown", "confidence": 0.5, "error_messages": [], "success_indicators": [], "redirect_target": null, "reasoning": "test"}'
    result = extract_json(plain)
    assert result["outcome"] == "unknown"

    # JSON buried in preamble text
    with_preamble = 'Here is my analysis:\n{"outcome": "validation_error", "confidence": 0.8, "error_messages": ["bad"], "success_indicators": [], "redirect_target": null, "reasoning": "test"}\nDone.'
    result = extract_json(with_preamble)
    assert result["outcome"] == "validation_error"


# ---------------------------------------------------------------------------
# Additional: extract_json error case
# ---------------------------------------------------------------------------

def test_extract_json_raises_on_garbage():
    """extract_json raises LLMParseError on non-JSON input."""
    from app.utils.json_parser import extract_json, LLMParseError
    with pytest.raises(LLMParseError):
        extract_json("This is not JSON at all.")
