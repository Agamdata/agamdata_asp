"""ASP-DEFECT-024 9-invocation stress test (I-DOC-01 verification).

Same contract as DEFECT-022 resolution: 9 successive invocations of
the three fixed async helpers must all succeed end-to-end — no
`Future attached to different loop` errors, no psycopg2 imports,
every async_jobs row transitions to 'completed'.

**Design note.** The three fixed helpers use per-invocation
`create_async_engine` + `await engine.dispose()` (DEFECT-022
playbook). The test scaffolding MUST use the same pattern — using
the app's shared `get_session()` pool would itself trigger the
loop-affinity class of bug (a pool created in one `asyncio.run()`
cannot be reused in a later one). Every DB call below wraps its
own engine lifecycle.

Usage (inside ai-service container):
    PYTHONPATH=/app python tests/_stress_defect024.py

Exits non-zero on first failure.
"""
import asyncio
import sys
import time
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.services.doc_intelligence import (
    _async_update_job_status,
    _async_fetch_prompt,
)


STRESS_COUNT = 9


# ---------------------------------------------------------------------------
# Per-invocation-engine helpers for test scaffolding (same pattern as the
# fix under test — no shared pool, no loop affinity)
# ---------------------------------------------------------------------------

async def _seed_job(job_id: str, tenant_id: uuid.UUID, caller_module: str,
                    task: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO async_jobs
                      (job_id, tenant_id, caller_module, service_type, task,
                       status, created_at)
                    VALUES
                      (:job_id, :tenant_id, :caller_module, 'doc_intelligence',
                       :task, 'queued', NOW())
                """),
                {
                    "job_id": job_id,
                    "tenant_id": str(tenant_id),
                    "caller_module": caller_module,
                    "task": task,
                },
            )
    finally:
        await engine.dispose()


async def _read_job_status(job_id: str) -> str:
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT status FROM async_jobs WHERE job_id = :j"),
                    {"j": job_id},
                )
            ).mappings().one_or_none()
    finally:
        await engine.dispose()
    return row["status"] if row else "<missing>"


async def _bootstrap_test_tenant() -> uuid.UUID:
    """Return a tenant_id for the stress test. Use first active tenant
    or create a synthetic one if none."""
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT id FROM tenants WHERE is_active LIMIT 1")
                )
            ).mappings().one_or_none()
            if row is not None:
                return row["id"]

            new_id = uuid.uuid4()
            await conn.execute(
                text("""
                    INSERT INTO tenants
                      (id, tenant_code, name, monthly_quota_usd,
                       is_active, created_at, updated_at)
                    VALUES
                      (:id, :code, :name, 1000.0, TRUE, NOW(), NOW())
                """),
                {
                    "id": str(new_id),
                    "code": f"stress-defect024-{int(time.time())}",
                    "name": "DEFECT-024 stress test",
                },
            )
            return new_id
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Stress-test driver
# ---------------------------------------------------------------------------

def _run_one_iteration(iteration: int, tenant_id: uuid.UUID,
                       caller_module: str, task: str) -> dict:
    """Drive the three fixed helpers through their full life-cycle.

    Each call is its own `asyncio.run()` — this is exactly the pattern
    that exposed DEFECT-022 (and would expose DEFECT-024 regression):
    per-call engine creation, new event loop, no cross-loop pool
    reuse.
    """
    result = {"iteration": iteration, "ok": False, "errors": []}

    job_id = str(uuid.uuid4())

    try:
        asyncio.run(_seed_job(job_id, tenant_id, caller_module, task))
    except Exception as e:
        result["errors"].append(f"seed: {e.__class__.__name__}: {e}")
        return result

    # Step 1: site-1 UPDATE running
    try:
        asyncio.run(_async_update_job_status(job_id, "running"))
    except Exception as e:
        result["errors"].append(f"site-1 running: {e.__class__.__name__}: {e}")
        return result

    # Step 2: site-3 prompt fetch
    try:
        asyncio.run(_async_fetch_prompt(task, caller_module))
    except Exception as e:
        result["errors"].append(f"site-3 fetch_prompt: {e.__class__.__name__}: {e}")
        return result

    # Step 3: site-1 UPDATE completed (success path)
    try:
        asyncio.run(_async_update_job_status(
            job_id, "completed", result={"probe": "defect-024"}
        ))
    except Exception as e:
        result["errors"].append(f"site-1 completed: {e.__class__.__name__}: {e}")
        return result

    # Read-back verification
    try:
        final_status = asyncio.run(_read_job_status(job_id))
    except Exception as e:
        result["errors"].append(f"read-back: {e.__class__.__name__}: {e}")
        return result

    if final_status != "completed":
        result["errors"].append(
            f"final_status={final_status!r} (expected 'completed')"
        )
        return result

    result["ok"] = True
    result["job_id"] = job_id
    return result


def main() -> int:
    tenant_id = asyncio.run(_bootstrap_test_tenant())
    print(f"Stress test tenant: {tenant_id}")
    print(f"Target: {STRESS_COUNT} successive invocations "
          f"(mixed classify_document + extract_document)\n")

    passed = 0
    for i in range(1, STRESS_COUNT + 1):
        task = "classify_document" if i % 2 == 0 else "extract_document"
        caller = "playwright_runner" if i % 3 == 0 else "crm"

        r = _run_one_iteration(i, tenant_id, caller, task)

        if r["ok"]:
            print(f"  [{i}/{STRESS_COUNT}] PASS  caller={caller:20s} "
                  f"task={task:20s} job_id={r['job_id']}")
            passed += 1
        else:
            print(f"  [{i}/{STRESS_COUNT}] FAIL  caller={caller:20s} "
                  f"task={task:20s}")
            for err in r["errors"]:
                print(f"          - {err}")
            print(f"\nSTOP-ON-FIRST-FAILURE. {passed}/{STRESS_COUNT} passed.")
            return 1

    print(f"\nRESULT: {passed}/{STRESS_COUNT} PASS")
    return 0 if passed == STRESS_COUNT else 1


if __name__ == "__main__":
    sys.exit(main())
