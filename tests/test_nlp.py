"""
Phase 2 acceptance tests — tests/test_nlp.py
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


NL_TO_SQL_MOCK_RESPONSE = json.dumps({
    "sql": "SELECT * FROM customers",
    "explanation": "All customers",
    "tables_used": ["customers"],
    "confidence": 0.95,
    "ambiguities": [],
})


@pytest.fixture
def nlp_authed_client(authed_client, mock_rag, mock_prompt_registry):
    """Authed client with RAG and prompt registry mocked."""
    return authed_client


# Test 5: nl_to_sql returns valid SQL (mocked Anthropic)
def test_nl_to_sql(nlp_authed_client, mock_anthropic):
    content_mock = MagicMock()
    content_mock.text = NL_TO_SQL_MOCK_RESPONSE
    usage_mock = MagicMock()
    usage_mock.input_tokens = 100
    usage_mock.output_tokens = 50
    response_mock = MagicMock()
    response_mock.content = [content_mock]
    response_mock.usage = usage_mock
    mock_anthropic.messages.create = AsyncMock(return_value=response_mock)

    # Also patch cost meter so it doesn't fail without DB
    with patch("app.gateway.router.emit_cost_event_from_gateway", new_callable=AsyncMock), \
         patch("app.gateway.router.check_quota", new_callable=AsyncMock, return_value=True):
        r = nlp_authed_client.post(
            "/api/v1/ai/invoke",
            json={
                "service_type": "nlp",
                "task": "nl_to_sql",
                "caller_module": "crm",
                "tenant_id": "test_tenant",
                "payload": {"query": "Show all customers"},
            },
        )

    assert r.status_code == 200, r.text
    data = r.json()
    assert "sql" in data["result"]
    assert data["result"]["sql"] == "SELECT * FROM customers"
    assert data["result"]["confidence"] > 0


# Test 6: exclude_tables is passed through to RAG
def test_exclude_tables_filters_chunks(nlp_authed_client, mock_rag, mock_anthropic):
    content_mock = MagicMock()
    content_mock.text = NL_TO_SQL_MOCK_RESPONSE
    usage_mock = MagicMock()
    usage_mock.input_tokens = 100
    usage_mock.output_tokens = 50
    response_mock = MagicMock()
    response_mock.content = [content_mock]
    response_mock.usage = usage_mock
    mock_anthropic.messages.create = AsyncMock(return_value=response_mock)

    with patch("app.gateway.router.emit_cost_event_from_gateway", new_callable=AsyncMock), \
         patch("app.gateway.router.check_quota", new_callable=AsyncMock, return_value=True):
        nlp_authed_client.post(
            "/api/v1/ai/invoke",
            json={
                "service_type": "nlp",
                "task": "nl_to_sql",
                "caller_module": "crm",
                "tenant_id": "test_tenant",
                "schema_hints": {"exclude_tables": ["salaries"]},
                "payload": {"query": "test"},
            },
        )

    mock_rag.assert_called_once()
    call_kwargs = mock_rag.call_args
    assert "salaries" in call_kwargs.kwargs.get("exclude_tables", call_kwargs.args[3] if len(call_kwargs.args) > 3 else [])


# Test 7: Unknown NLP task returns 400
def test_unknown_nlp_task(nlp_authed_client):
    with patch("app.gateway.router.check_quota", new_callable=AsyncMock, return_value=True):
        r = nlp_authed_client.post(
            "/api/v1/ai/invoke",
            json={
                "service_type": "nlp",
                "task": "unknown_task_xyz",
                "caller_module": "crm",
                "tenant_id": "test_tenant",
                "payload": {},
            },
        )
    assert r.status_code == 400
