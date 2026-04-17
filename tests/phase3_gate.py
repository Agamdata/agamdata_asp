"""Phase 3 gate — 17 ACs for I-04, I-06, I-07, I-11, I-12, I-13.

Uses httpx.AsyncClient + ASGITransport so the test, the app, and the
asyncpg pool all share a single event loop (avoids TestClient's
BlockingPortal issue). Fixtures created and torn down under throwaway
test tenants.
"""
import asyncio
import logging
import uuid

import bcrypt
import httpx
import structlog
from httpx import ASGITransport
from sqlalchemy import delete, select

from app.infra.db import get_session
from app.main import app
from app.models.db_models import AsyncJob, CostEvent, Tenant, TenantApiKey
from app.models.response import InvokeResponse, JobAcceptedResponse, ResponseMeta
from app.utils.key_generator import generate_api_key

# --- Stub handlers (avoid real LLM calls during Phase 3 gate) ---
# Gateway routing, auth, caller_feature plumbing, X-Request-Id, 202 handling,
# cost emission — all exercised. Handlers themselves are replaced with
# deterministic stubs so the test does not depend on Anthropic availability.
from app.gateway import router as _gw_router


async def _stub_sync(req, model, request_id):
    return InvokeResponse(
        request_id=request_id,
        service_type=req.service_type,
        task=req.task,
        result={"stub": True, "task": req.task},
        meta=ResponseMeta(
            model=model, input_tokens=10, output_tokens=5,
            cost_usd=0.0001, latency_ms=1,
        ),
    )


async def _stub_async(req, model, request_id):
    # Gateway uses JobAcceptedResponse shape; meta is carried for cost emission
    # even though async services self-emit on completion.
    class _AsyncResult:
        def __init__(self):
            self.request_id = request_id
            self.job_id = "job_stub_" + uuid.uuid4().hex[:8]
            self.status = "queued"
            self.message = "stubbed async job"
            self.meta = ResponseMeta(
                model=model, input_tokens=0, output_tokens=0,
                cost_usd=0.0, latency_ms=0,
            )
        def model_dump(self):
            return {
                "request_id": self.request_id,
                "job_id": self.job_id,
                "status": self.status,
                "message": self.message,
            }
    return _AsyncResult()


_gw_router.SERVICE_MAP = {
    "nlp": _stub_sync,
    "generation": _stub_sync,
    "dashboard_intelligence": _stub_sync,
    "doc_intelligence": _stub_async,
    "prediction": _stub_async,
}

# --- In-memory structlog log capture ---
captured_logs = []


class _CaptureProcessor:
    def __call__(self, logger, method_name, event_dict):
        captured_logs.append(dict(event_dict))
        return event_dict


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        _CaptureProcessor(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
)

TEST_TENANT_ID = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-000000000002")
OTHER_TENANT_ID = uuid.UUID("cccccccc-dddd-eeee-ffff-000000000003")


async def setup():
    async with get_session() as s:
        await s.execute(delete(AsyncJob).where(AsyncJob.tenant_id.in_([TEST_TENANT_ID, OTHER_TENANT_ID])))
        await s.execute(delete(CostEvent).where(CostEvent.tenant_id.in_([TEST_TENANT_ID, OTHER_TENANT_ID])))
        await s.execute(delete(TenantApiKey).where(TenantApiKey.tenant_id.in_([TEST_TENANT_ID, OTHER_TENANT_ID])))
        await s.execute(delete(Tenant).where(Tenant.id.in_([TEST_TENANT_ID, OTHER_TENANT_ID])))
        await s.commit()

        s.add(Tenant(id=TEST_TENANT_ID, tenant_code="ph3_" + uuid.uuid4().hex[:6],
                     name="Phase3 Tenant", monthly_quota_usd=100.0, is_active=True))
        s.add(Tenant(id=OTHER_TENANT_ID, tenant_code="ph3_other_" + uuid.uuid4().hex[:6],
                     name="Phase3 Other Tenant", monthly_quota_usd=100.0, is_active=True))
        await s.flush()

        raw_new, prefix_new, hash_new = generate_api_key()
        s.add(TenantApiKey(tenant_id=TEST_TENANT_ID, key_prefix=prefix_new,
                           api_key_hash=hash_new, label="test_new", is_active=True))

        raw_legacy = "legacy_test_key_phase3_xyz"
        hash_legacy = bcrypt.hashpw(raw_legacy.encode(), bcrypt.gensalt()).decode()
        s.add(TenantApiKey(tenant_id=TEST_TENANT_ID,
                           key_prefix="leg_" + uuid.uuid4().hex[:8],
                           api_key_hash=hash_legacy, label="legacy", is_active=True))

        raw_other, prefix_other, hash_other = generate_api_key()
        s.add(TenantApiKey(tenant_id=OTHER_TENANT_ID, key_prefix=prefix_other,
                           api_key_hash=hash_other, label="other_test", is_active=True))

        test_job_id = "job_" + uuid.uuid4().hex[:10]
        other_job_id = "job_" + uuid.uuid4().hex[:10]
        s.add(AsyncJob(job_id=test_job_id, tenant_id=TEST_TENANT_ID, status="completed",
                       service_type="doc_intelligence", task="extract", caller_module="test"))
        s.add(AsyncJob(job_id=other_job_id, tenant_id=OTHER_TENANT_ID, status="completed",
                       service_type="doc_intelligence", task="extract", caller_module="test"))

        await s.commit()
    return raw_new, raw_legacy, raw_other, test_job_id, other_job_id


async def teardown():
    async with get_session() as s:
        await s.execute(delete(AsyncJob).where(AsyncJob.tenant_id.in_([TEST_TENANT_ID, OTHER_TENANT_ID])))
        await s.execute(delete(CostEvent).where(CostEvent.tenant_id.in_([TEST_TENANT_ID, OTHER_TENANT_ID])))
        await s.execute(delete(TenantApiKey).where(TenantApiKey.tenant_id.in_([TEST_TENANT_ID, OTHER_TENANT_ID])))
        await s.execute(delete(Tenant).where(Tenant.id.in_([TEST_TENANT_ID, OTHER_TENANT_ID])))
        await s.commit()


async def cost_rows_for(tenant_id, **filters):
    async with get_session() as s:
        q = select(CostEvent).where(CostEvent.tenant_id == tenant_id)
        for k, v in filters.items():
            col = getattr(CostEvent, k)
            q = q.where(col.is_(None) if v is None else (col == v))
        return (await s.execute(q)).scalars().all()


async def run():
    raw_new, raw_legacy, raw_other, test_job_id, other_job_id = await setup()
    transport = ASGITransport(app=app)
    results = []

    def check(label, cond, info=""):
        results.append((label, "PASS" if cond else "FAIL", info))

    nlp_payload = {"query": "ping"}

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        # AC-S1-01
        captured_logs.clear()
        resp = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                  "caller_feature": "F-03-08", "tenant_id": str(TEST_TENANT_ID),
                  "payload": nlp_payload})
        auth_ok = any(l.get("event") == "auth_success" and l.get("path") == "new_format"
                      for l in captured_logs)
        check("AC-S1-01 new-format key authenticates + log",
              auth_ok and resp.status_code in (200, 500),
              f"http={resp.status_code} auth_success_new_format={auth_ok}")

        # AC-S1-02
        resp = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": "asp_aaaaaaaaaaaa_ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                  "tenant_id": str(TEST_TENANT_ID), "payload": {}})
        body = {}
        try: body = resp.json()
        except Exception: pass
        is_rfc7807 = (resp.status_code == 401
                      and resp.headers.get("content-type", "").startswith("application/problem+json")
                      and set(body.keys()) == {"type","title","status","detail","instance","request_id"}
                      and body.get("status") == 401)
        check("AC-S1-02 invalid key -> 401 RFC 7807", is_rfc7807,
              f"status={resp.status_code} ctype={resp.headers.get('content-type')} keys={sorted(body.keys())}")

        # AC-S1-03
        captured_logs.clear()
        resp = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_legacy},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                  "tenant_id": str(TEST_TENANT_ID), "payload": nlp_payload})
        legacy_log = any(l.get("event") == "auth_legacy_path_used" and l.get("sunset")
                         for l in captured_logs)
        auth_leg = any(l.get("event") == "auth_success" and l.get("path") == "legacy"
                       for l in captured_logs)
        check("AC-S1-03 legacy key authenticates + sunset log",
              legacy_log and auth_leg and resp.status_code in (200, 500),
              f"http={resp.status_code} legacy_log={legacy_log} auth_success_legacy={auth_leg}")

        # AC-S1-04
        import bcrypt as _bc
        _orig = _bc.checkpw
        counter = {"n": 0}
        def _counting(p, h):
            counter["n"] += 1
            return _orig(p, h)
        _bc.checkpw = _counting
        try:
            counter["n"] = 0
            await client.post("/api/v1/ai/invoke",
                headers={"X-ASP-API-Key": raw_new},
                json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                      "tenant_id": str(TEST_TENANT_ID), "payload": nlp_payload})
            bcrypt_count = counter["n"]
        finally:
            _bc.checkpw = _orig
        check("AC-S1-04 new-format = exactly 1 bcrypt call",
              bcrypt_count == 1,
              f"bcrypt.checkpw called {bcrypt_count} times")

        # AC-S6-01
        captured_logs.clear()
        await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                  "caller_feature": "F-03-08", "tenant_id": str(TEST_TENANT_ID),
                  "payload": nlp_payload})
        invoke_start = [l for l in captured_logs if l.get("event") == "invoke_start"]
        cf_on_start = any(l.get("caller_feature") == "F-03-08" for l in invoke_start)
        downstream = [l for l in captured_logs
                      if l.get("event") in ("invoke_complete","invoke_failed",
                                            "gateway_cost_emission_failed","quota_exceeded")]
        cf_downstream = (all(l.get("caller_feature") == "F-03-08" for l in downstream)
                         if downstream else True)
        check("AC-S6-01 caller_feature in invoke_start + downstream ctx",
              cf_on_start and cf_downstream,
              f"start_cf={cf_on_start} downstream_events={len(downstream)} all_cf={cf_downstream}")

        # Small delay for commit
        await asyncio.sleep(0.3)
        rows = await cost_rows_for(TEST_TENANT_ID, caller_feature="F-03-08")
        check("AC-S6-02 cost_events has caller_feature=F-03-08",
              len(rows) >= 1, f"rows={len(rows)}")

        # AC-S6-03
        captured_logs.clear()
        resp = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST_NOFEAT",
                  "tenant_id": str(TEST_TENANT_ID), "payload": nlp_payload})
        no422 = resp.status_code != 422
        invoke_start = [l for l in captured_logs if l.get("event") == "invoke_start"]
        cf_null = all(l.get("caller_feature") is None for l in invoke_start)
        await asyncio.sleep(0.3)
        nrows = await cost_rows_for(TEST_TENANT_ID, caller_module="TEST_NOFEAT", caller_feature=None)
        check("AC-S6-03 caller_feature absent -> null + no 422",
              no422 and cf_null and len(nrows) >= 1,
              f"http={resp.status_code} cf_null={cf_null} null_rows={len(nrows)}")

        # AC-S6-04
        resp1 = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                  "caller_feature": "F-03-04", "tenant_id": str(TEST_TENANT_ID),
                  "payload": nlp_payload})
        resp2 = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                  "caller_feature": "F-01-10", "tenant_id": str(TEST_TENANT_ID),
                  "payload": nlp_payload})
        await asyncio.sleep(0.3)
        async with get_session() as s:
            r = await s.execute(
                select(CostEvent.service_type, CostEvent.task, CostEvent.caller_feature)
                .where(CostEvent.tenant_id == TEST_TENANT_ID,
                       CostEvent.caller_feature.in_(["F-03-04","F-01-10"])))
            rrows = r.all()
        consistent = (all(row[0] == "nlp" and row[1] == "intent_extraction" for row in rrows)
                      and len(rrows) >= 2)
        same_http = resp1.status_code == resp2.status_code
        check("AC-S6-04 same service/task -> same routing regardless of caller_feature",
              same_http and consistent,
              f"same_http={same_http} rows={rrows}")

        # AC-S6-05
        resp = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                  "caller_feature": "x" * 129, "tenant_id": str(TEST_TENANT_ID),
                  "payload": {}})
        check("AC-S6-05 caller_feature 129 chars -> 422",
              resp.status_code == 422,
              f"http={resp.status_code}")

        # AC-S8-01
        resp = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "doc_intelligence", "task": "extract_document",
                  "caller_module": "TEST", "tenant_id": str(TEST_TENANT_ID),
                  "payload": {"object_key": "test.pdf"}})
        body = {}
        try: body = resp.json()
        except Exception: pass
        check("AC-S8-01 doc_intel -> 202 + job_id",
              resp.status_code == 202 and "job_id" in body,
              f"http={resp.status_code} keys={sorted(body.keys()) if body else 'n/a'}")

        # AC-S8-02
        resp = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "generation", "task": "summarise_customer",
                  "caller_module": "TEST", "tenant_id": str(TEST_TENANT_ID),
                  "payload": {"content": "This is a short text for summarisation.",
                              "max_sentences": 2}})
        has_result = False
        try:
            b = resp.json()
            has_result = isinstance(b.get("result"), dict)
        except Exception:
            pass
        check("AC-S8-02 generation -> 200 + result{}",
              resp.status_code == 200 and has_result,
              f"http={resp.status_code} has_result_dict={has_result}")

        # AC-S8-03
        resp = await client.get("/api/v1/ai/jobs/" + test_job_id,
                                 headers={"X-ASP-API-Key": raw_new})
        body = {}
        try: body = resp.json()
        except Exception: pass
        check("AC-S8-03 GET /jobs/{own} -> 200",
              resp.status_code == 200 and body.get("job_id") == test_job_id,
              f"http={resp.status_code} got_job_id={body.get('job_id')}")

        # AC-S8-04
        resp = await client.get("/api/v1/ai/jobs/" + other_job_id,
                                 headers={"X-ASP-API-Key": raw_new})
        check("AC-S8-04 GET /jobs/{other_tenant} -> 404 (never 403)",
              resp.status_code == 404,
              f"http={resp.status_code}")

        # AC-CC-04
        resp = await client.post("/api/v1/ai/invoke",
            headers={"X-ASP-API-Key": raw_new},
            json={"service_type": "nlp", "task": "intent_extraction", "caller_module": "TEST",
                  "tenant_id": str(TEST_TENANT_ID), "payload": nlp_payload})
        hdr_rid = resp.headers.get("x-request-id")
        resp2 = await client.get("/api/v1/ai/jobs/" + test_job_id,
                                  headers={"X-ASP-API-Key": raw_new})
        hdr_rid2 = resp2.headers.get("x-request-id")
        check("AC-CC-04 X-Request-Id header on success responses",
              hdr_rid is not None and hdr_rid2 is not None,
              f"invoke_xrid={hdr_rid} jobs_xrid={hdr_rid2}")

    print()
    print("=" * 95)
    for name, status, info in results:
        print(f"  [{status}] {name:<62}  {info}")
    print("=" * 95)
    n_pass = sum(1 for _, s, _ in results if s == "PASS")
    n_fail = sum(1 for _, s, _ in results if s != "PASS")
    print(f"\n  SUMMARY: {n_pass} PASS / {n_fail} FAIL of {len(results)}")

    await teardown()
    print("Teardown: OK")
    return n_fail


if __name__ == "__main__":
    rc = asyncio.run(run())
    raise SystemExit(rc)
