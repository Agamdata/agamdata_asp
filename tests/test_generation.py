"""
Tests for ASP-03 Generation Service — generate_test_cases task.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch


# ── Fixtures ──────────────────────────────────────────────────────────────────

VALID_GENERATE_TC_PAYLOAD = {
    "service_type": "generation",
    "task": "generate_test_cases",
    "caller_module": "playwright_runner",
    "tenant_id": "test_tenant",
    "quality_tier": "enhanced",
    "payload": {
        "url": "https://github.com/login",
        "snapshot_text": "role: textbox  name: \"Username or email address\"\nrole: button  name: \"Sign in\"",
        "interactive_elements": [
            {
                "tag": "input", "role": "textbox",
                "name": "Username or email address",
                "type": "text", "testid": "", "id": "login_field", "forLabel": ""
            }
        ],
        "page_title": "Sign in to GitHub",
        "locator_source": "snapshot"
    }
}

MOCK_LLM_RESPONSE = json.dumps({
    "page_analysis": {
        "page_type": "authentication",
        "complexity": "low",
        "summary": "GitHub login page",
        "primary_flows": ["login with credentials"],
        "detected_elements": ["username input", "password input", "submit button"],
        "tech_stack_hints": ["React"]
    },
    "test_cases": [
        {
            "id": "TC-001",
            "name": "Login with valid credentials",
            "priority": "Critical",
            "category": "Authentication",
            "description": "User can log in with correct username and password",
            "preconditions": "Valid GitHub account exists",
            "steps": [
                {"step_number": 1, "action": "navigate", "target": "https://github.com/login", "value": None, "description": "Open login page"},
                {"step_number": 2, "action": "fill", "target": "getByLabel(\"Username or email address\")", "value": "testuser", "description": "Enter username"},
                {"step_number": 3, "action": "fill", "target": "getByLabel(\"Password\")", "value": "password123", "description": "Enter password"},
                {"step_number": 4, "action": "click", "target": "getByRole(\"button\",{\"name\":\"Sign in\"})", "value": None, "description": "Click sign in"}
            ],
            "locators": {
                "username_input": {"primary": "getByLabel(\"Username or email address\")", "fallback": "#login_field", "strategy": "label-text — stable"},
                "sign_in_button": {"primary": "getByRole(\"button\",{\"name\":\"Sign in\"})", "fallback": None, "strategy": "aria-role — survives CSS changes"}
            },
            "seed_data": {
                "valid": {"username": "testuser@example.com", "password": "SecurePass123!"},
                "invalid_format": {"username": "not-an-email", "password": "123"}
            },
            "expected_result": "User is redirected to GitHub dashboard",
            "playwright_notes": "Use page.waitForURL after click"
        }
    ]
})


def _mock_response(text):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=500, output_tokens=1200)
    return resp


GATEWAY_PATCHES = dict(
    check_quota=patch("app.cost.meter.check_quota", new=AsyncMock(return_value=True)),
    emit_cost=patch("app.gateway.router.emit_cost_event_from_gateway", new=AsyncMock()),
)


# ── Test 1: Valid request returns correct structure ───────────────────────────

def test_generate_test_cases_returns_structure(authed_client, mock_prompt_registry):
    with patch("app.cost.meter.check_quota", new=AsyncMock(return_value=True)), \
         patch("app.gateway.router.emit_cost_event_from_gateway", new=AsyncMock()), \
         patch("app.services.generation.anthropic_client") as mock_llm:
        mock_llm.messages.create = AsyncMock(return_value=_mock_response(MOCK_LLM_RESPONSE))
        r = authed_client.post("/api/v1/ai/invoke", json=VALID_GENERATE_TC_PAYLOAD)

    assert r.status_code == 200
    data = r.json()
    assert data["service_type"] == "generation"
    assert data["task"] == "generate_test_cases"
    assert "page_analysis" in data["result"]
    assert "test_cases" in data["result"]
    assert len(data["result"]["test_cases"]) >= 1
    assert data["meta"]["cost_usd"] >= 0


# ── Test 2: Snapshot text injected into LLM call ─────────────────────────────

def test_snapshot_injected_in_user_message(authed_client, mock_prompt_registry):
    captured_messages = []

    async def capture(*args, **kwargs):
        captured_messages.append(kwargs.get("messages", []))
        return _mock_response(MOCK_LLM_RESPONSE)

    with patch("app.cost.meter.check_quota", new=AsyncMock(return_value=True)), \
         patch("app.gateway.router.emit_cost_event_from_gateway", new=AsyncMock()), \
         patch("app.services.generation.anthropic_client") as mock_llm:
        mock_llm.messages.create = capture
        authed_client.post("/api/v1/ai/invoke", json=VALID_GENERATE_TC_PAYLOAD)

    assert captured_messages
    user_msg = captured_messages[0][0]["content"]
    assert "ACCESSIBILITY TREE" in user_msg
    assert "Username or email address" in user_msg


# ── Test 3: Missing snapshot degrades gracefully ──────────────────────────────

def test_inferred_locator_source_degrades_gracefully(authed_client, mock_prompt_registry):
    payload_no_snapshot = {**VALID_GENERATE_TC_PAYLOAD}
    payload_no_snapshot["payload"] = {
        "url": "https://github.com/login",
        "locator_source": "inferred",
    }

    captured_messages = []

    async def capture(*args, **kwargs):
        captured_messages.append(kwargs.get("messages", []))
        return _mock_response(MOCK_LLM_RESPONSE)

    with patch("app.cost.meter.check_quota", new=AsyncMock(return_value=True)), \
         patch("app.gateway.router.emit_cost_event_from_gateway", new=AsyncMock()), \
         patch("app.services.generation.anthropic_client") as mock_llm:
        mock_llm.messages.create = capture
        r = authed_client.post("/api/v1/ai/invoke", json=payload_no_snapshot)

    assert r.status_code == 200
    user_msg = captured_messages[0][0]["content"]
    assert "ACCESSIBILITY TREE" not in user_msg
    assert "infer" in user_msg.lower()


# ── Test 4: Invalid payload rejected before LLM call ─────────────────────────

def test_invalid_payload_rejected(authed_client):
    bad_payload = {**VALID_GENERATE_TC_PAYLOAD}
    bad_payload["payload"] = {"locator_source": "bad_value"}  # missing url, bad enum

    with patch("app.cost.meter.check_quota", new=AsyncMock(return_value=True)), \
         patch("app.gateway.router.emit_cost_event_from_gateway", new=AsyncMock()):
        r = authed_client.post("/api/v1/ai/invoke", json=bad_payload)

    assert r.status_code == 422
