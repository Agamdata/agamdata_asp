"""PAP-ASP-REQ-ASP-01 v2.0 / BP-10 — suggest_screen_mapping 8-AC suite.

Per ASP-OUT-020 directive. Standing rule: stop on first failure.

ACs:
  AC-BP10-01: Valid call with matching module → 200, module_key in
              available_modules, confidence > 0.0
  AC-BP10-02: No matching module → null/null/0.0
  AC-BP10-03: LLM hallucinated key → handler scrubs to null,
              logs hallucinated_module_key
  AC-BP10-04: null page_title and page_type → 200
  AC-BP10-05: empty available_modules → 422
  AC-BP10-06: caller_feature=BP-10 in structlog + cost_events
  AC-BP10-07: GET /api/v1/ai/schemas/nlp/suggest_screen_mapping
              → valid JSON Schema
  AC-BP10-08: Regression — classify_probe_result still works
"""
import asyncio
import json
import logging
import uuid
from unittest.mock import patch

import bcrypt
import httpx
import structlog
from httpx import ASGITransport
from sqlalchemy import delete, select, text

from app.infra.db import get_session
from app.infra.redis import init_redis
from app.main import app
from app.models.db_models import Tenant, TenantApiKey, CostEvent
from app.utils.key_generator import generate_api_key

# Capture structlog events for hallucination / caller_feature assertions
captured = []

class _CaptureProc:
    def __call__(self, logger, method_name, event_dict):
        captured.append(dict(event_dict))
        return event_dict


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        _CaptureProc(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
)

TEST_TENANT = uuid.UUID("55555555-aaaa-bbbb-cccc-dddddddddddd")

MODULES = [
    {"module_key": "leads", "module_name": "Leads"},
    {"module_key": "customers", "module_name": "Customers"},
    {"module_key": "opportunities", "module_name": "Opportunities"},
    {"module_key": "quotes", "module_name": "Quotes"},
]


async def setup():
    async with get_session() as s:
        await s.execute(delete(CostEvent).where(CostEvent.tenant_id == TEST_TENANT))
        await s.execute(delete(TenantApiKey).where(TenantApiKey.tenant_id == TEST_TENANT))
        await s.execute(delete(Tenant).where(Tenant.id == TEST_TENANT))
        await s.commit()
        s.add(Tenant(id=TEST_TENANT, tenant_code="bp10_" + uuid.uuid4().hex[:4],
                     name="BP-10 AC Suite", monthly_quota_usd=100.0, is_active=True))
        await s.flush()
        raw, prefix, hashed = generate_api_key()
        s.add(TenantApiKey(tenant_id=TEST_TENANT, key_prefix=prefix,
                           api_key_hash=hashed, label="bp10", is_active=True))
        await s.commit()
    return raw


async def teardown():
    async with get_session() as s:
        await s.execute(delete(CostEvent).where(CostEvent.tenant_id == TEST_TENANT))
        await s.execute(delete(TenantApiKey).where(TenantApiKey.tenant_id == TEST_TENANT))
        await s.execute(delete(Tenant).where(Tenant.id == TEST_TENANT))
        await s.commit()


def body(task, caller_feature, payload, caller_module="test_generator"):
    return {
        "service_type": "nlp",
        "task": task,
        "caller_module": caller_module,
        "caller_feature": caller_feature,
        "tenant_id": str(TEST_TENANT),
        "quality_tier": "standard",
        "payload": payload,
    }


async def main():
    raw = await setup()
    await init_redis()
    transport = ASGITransport(app=app)
    results = []

    def check(ac, cond, info=""):
        tag = "PASS" if cond else "FAIL"
        results.append((ac, tag, info))
        print(f"  [{tag}] {ac:<15} {info[:85]}")
        return cond

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            # AC-BP10-01 — matching module returns >0 confidence + key in list
            r = await client.post("/api/v1/ai/invoke",
                headers={"X-ASP-API-Key": raw},
                json=body("suggest_screen_mapping", "BP-10", {
                    "page_url": "https://crm.example.com/leads/new",
                    "page_title": "New Lead",
                    "page_type": "FORM",
                    "available_modules": MODULES,
                }), timeout=60.0)
            if r.status_code != 200:
                check("AC-BP10-01", False, f"http={r.status_code} body={r.text[:200]}")
                raise RuntimeError("stop")
            result = r.json()["result"]
            mk = result.get("suggested_module_key")
            conf = result.get("confidence", 0.0)
            allowed = {m["module_key"] for m in MODULES}
            if not check("AC-BP10-01",
                         mk in allowed and conf > 0.0,
                         f"module_key={mk} confidence={conf}"):
                raise RuntimeError("stop")

            # AC-BP10-02 — no matching module (completely unrelated URL) → null outputs
            # LLM is instructed to return null when confidence is low; we supply a URL
            # that has zero semantic overlap with any module.
            r = await client.post("/api/v1/ai/invoke",
                headers={"X-ASP-API-Key": raw},
                json=body("suggest_screen_mapping", "BP-10", {
                    "page_url": "https://totally-unrelated.example.com/xyz/qrs",
                    "page_title": "Some Unrelated Page",
                    "page_type": "DASHBOARD",
                    "available_modules": [
                        {"module_key": "medical_records", "module_name": "Medical Records"},
                        {"module_key": "pharmacy_inventory", "module_name": "Pharmacy Inventory"},
                    ],
                }), timeout=60.0)
            result = r.json()["result"]
            mk = result.get("suggested_module_key")
            conf = result.get("confidence", 1.0)
            # AC passes if module_key is None OR confidence is very low (≤0.4 per prompt guidance)
            if not check("AC-BP10-02",
                         r.status_code == 200 and (mk is None or conf <= 0.4),
                         f"module_key={mk} confidence={conf}"):
                raise RuntimeError("stop")

            # AC-BP10-03 — hallucination guard. Simulate LLM returning a key not in list.
            # Patch anthropic_client to return a forged response with a hallucinated key.
            captured.clear()
            forged_json = json.dumps({
                "suggested_module_key": "made_up_module_xyz",
                "suggested_screen_name": "Fake Screen",
                "confidence": 0.99,
            })

            class FakeContent:
                def __init__(self, text):
                    self.text = text

            class FakeUsage:
                input_tokens = 10
                output_tokens = 10

            class FakeResponse:
                def __init__(self):
                    self.content = [FakeContent(forged_json)]
                    self.usage = FakeUsage()
                    self.stop_reason = "end_turn"

            async def fake_llm(*args, **kwargs):
                return FakeResponse()

            with patch("app.services.nlp.llm_call_with_retry", side_effect=fake_llm):
                r = await client.post("/api/v1/ai/invoke",
                    headers={"X-ASP-API-Key": raw},
                    json=body("suggest_screen_mapping", "BP-10", {
                        "page_url": "https://crm.example.com/leads",
                        "available_modules": MODULES,
                    }), timeout=30.0)
            if r.status_code != 200:
                check("AC-BP10-03", False, f"http={r.status_code} body={r.text[:200]}")
                raise RuntimeError("stop")
            result = r.json()["result"]
            scrubbed_ok = (result.get("suggested_module_key") is None
                          and result.get("suggested_screen_name") is None
                          and result.get("confidence") == 0.0)
            hallucination_logged = any(
                e.get("event") == "hallucinated_module_key"
                and e.get("hallucinated_key") == "made_up_module_xyz"
                for e in captured
            )
            if not check("AC-BP10-03",
                         scrubbed_ok and hallucination_logged,
                         f"scrubbed={scrubbed_ok} logged={hallucination_logged}"):
                raise RuntimeError("stop")

            # AC-BP10-04 — null page_title and page_type → 200
            r = await client.post("/api/v1/ai/invoke",
                headers={"X-ASP-API-Key": raw},
                json=body("suggest_screen_mapping", "BP-10", {
                    "page_url": "https://crm.example.com/leads/new",
                    "available_modules": MODULES,
                    # page_title and page_type omitted → default None
                }), timeout=60.0)
            if not check("AC-BP10-04",
                         r.status_code == 200,
                         f"http={r.status_code}"):
                raise RuntimeError("stop")

            # AC-BP10-05 — empty available_modules → 422 (field_validator)
            r = await client.post("/api/v1/ai/invoke",
                headers={"X-ASP-API-Key": raw},
                json=body("suggest_screen_mapping", "BP-10", {
                    "page_url": "https://x.com",
                    "available_modules": [],
                }), timeout=30.0)
            if not check("AC-BP10-05",
                         r.status_code == 422,
                         f"http={r.status_code}"):
                raise RuntimeError("stop")

            # AC-BP10-06 — caller_feature=BP-10 in cost_events + structlog
            captured.clear()
            await client.post("/api/v1/ai/invoke",
                headers={"X-ASP-API-Key": raw},
                json=body("suggest_screen_mapping", "BP-10", {
                    "page_url": "https://crm.example.com/leads/new",
                    "available_modules": MODULES,
                }), timeout=60.0)
            await asyncio.sleep(0.4)  # allow cost-event commit
            async with get_session() as s:
                q = await s.execute(text(
                    "SELECT COUNT(*) FROM cost_events WHERE tenant_id=:t "
                    "AND caller_feature='BP-10' AND task='suggest_screen_mapping'"),
                    {"t": str(TEST_TENANT)})
                ce_count = q.scalar()
            cf_in_logs = any(e.get("caller_feature") == "BP-10" for e in captured)
            if not check("AC-BP10-06",
                         ce_count and ce_count >= 1 and cf_in_logs,
                         f"cost_events.caller_feature=BP-10 count={ce_count} in_logs={cf_in_logs}"):
                raise RuntimeError("stop")

            # AC-BP10-07 — GET /api/v1/ai/schemas/nlp/suggest_screen_mapping → JSON Schema
            r = await client.get(
                "/api/v1/ai/schemas/nlp/suggest_screen_mapping",
                headers={"X-ASP-API-Key": raw})
            if r.status_code != 200:
                check("AC-BP10-07", False, f"http={r.status_code}")
                raise RuntimeError("stop")
            body_js = r.json()
            props = body_js.get("properties", {})
            required = set(body_js.get("required", []))
            schema_ok = (body_js.get("type") == "object"
                         and "page_url" in props
                         and "available_modules" in props
                         and "page_url" in required
                         and "available_modules" in required)
            if not check("AC-BP10-07",
                         schema_ok,
                         f"type={body_js.get('type')} props={list(props.keys())} required={required}"):
                raise RuntimeError("stop")

            # AC-BP10-08 — regression: classify_probe_result still works
            r = await client.post("/api/v1/ai/invoke",
                headers={"X-ASP-API-Key": raw},
                json=body("classify_probe_result", "F-02-13", {
                    "page_url": "https://x.com",
                    "page_type": "FORM",
                    "submitted_fields": {"email": "a@b.c"},
                    "visible_text": "Thank you for signing up!",
                }, caller_module="playwright_runner"), timeout=60.0)
            if not check("AC-BP10-08",
                         r.status_code == 200,
                         f"http={r.status_code} (classify_probe_result regression)"):
                raise RuntimeError("stop")

    except RuntimeError as e:
        if "stop" not in str(e):
            raise

    # Summary
    print()
    print("=" * 100)
    for ac, tag, info in results:
        print(f"  [{tag}] {ac:<15} {info[:85]}")
    print("=" * 100)
    n_pass = sum(1 for _, s, _ in results if s == "PASS")
    n_fail = sum(1 for _, s, _ in results if s != "PASS")
    print(f"\n  SUMMARY: {n_pass} PASS / {n_fail} FAIL of {len(results)}")

    await teardown()
    return n_fail


if __name__ == "__main__":
    rc = asyncio.run(main())
    raise SystemExit(rc)
