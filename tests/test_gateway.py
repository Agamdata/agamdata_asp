"""
Phase 1 acceptance tests — tests/test_gateway.py
"""
import pytest


# Test 1: Health check
def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# Test 2: Missing API key returns 401
def test_missing_api_key(client):
    r = client.post(
        "/api/v1/ai/invoke",
        json={
            "service_type": "nlp",
            "task": "nl_to_sql",
            "caller_module": "crm",
            "tenant_id": "test_tenant",
            "payload": {"query": "test"},
        },
    )
    assert r.status_code == 401


# Test 3: Invalid service_type returns 400
def test_invalid_service_type(authed_client):
    r = authed_client.post(
        "/api/v1/ai/invoke",
        json={
            "service_type": "invalid",
            "task": "x",
            "caller_module": "crm",
            "tenant_id": "test_tenant",
            "payload": {},
        },
    )
    # Pydantic rejects unknown service_type with 422 (literal validation)
    assert r.status_code in (400, 422)


# Test 4: Unknown field rejected (extra="forbid")
def test_extra_field_rejected(authed_client):
    r = authed_client.post(
        "/api/v1/ai/invoke",
        json={
            "service_type": "nlp",
            "task": "nl_to_sql",
            "caller_module": "crm",
            "tenant_id": "test_tenant",
            "payload": {},
            "unknown_field": "x",
        },
    )
    assert r.status_code == 422


# Test 5: Version check in health response
def test_health_version(client):
    r = client.get("/api/v1/health")
    data = r.json()
    assert "version" in data
    assert data["version"] == "1.0.0"
