"""ASP-DEFECT-025 9-invocation stress test (prediction.py remediation).

Same contract as DEFECT-022 / DEFECT-024 resolutions: 9 successive
invocations of the three fixed async helpers must all succeed
end-to-end — no `Future attached to different loop` errors, no
psycopg2 imports, every async_jobs row transitions to 'completed'.

Usage (inside ai-service container):
    PYTHONPATH=/app python tests/_stress_defect025.py

Exits non-zero on first failure.
"""
import asyncio
import sys
import time
import uuid
from unittest.mock import MagicMock

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.services.prediction import (
    _async_update_job_status,
    _async_emit_cost,
)


STRESS_COUNT = 9


class _FakeUsage:
    def __init__(self):
        self.input_tokens = 25
        self.output_tokens = 40


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
                      (:job_id, :tenant_id, :caller_module, 'prediction',
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
                    "code": f"stress-defect025-{int(time.time())}",
                    "name": "DEFECT-025 stress test",
                },
            )
            return new_id
    finally:
        await engine.dispose()


def _run_one_iteration(iteration: int, tenant_id: uuid.UUID,
                       caller_module: str, task: str) -> dict:
    """Drive the three fixed helpers through their full life-cycle.

    Each call is its own `asyncio.run()` — reproduces the exact
    pattern that exposes loop-affinity bugs.
    """
    result = {"iteration": iteration, "ok": False, "errors": []}

    job_id = str(uuid.uuid4())

    try:
        asyncio.run(_seed_job(job_id, tenant_id, caller_module, task))
    except Exception as e:
        result["errors"].append(f"seed: {e.__class__.__name__}: {e}")
        return result

    # Step 1: UPDATE running
    try:
        asyncio.run(_async_update_job_status(job_id, "running"))
    except Exception as e:
        result["errors"].append(f"update_running: {e.__class__.__name__}: {e}")
        return result

    # Step 2: UPDATE completed
    try:
        asyncio.run(_async_update_job_status(
            job_id, "completed",
            result={"probe": "defect-025", "scores": {}, "confidence": 0.8},
        ))
    except Exception as e:
        result["errors"].append(f"update_completed: {e.__class__.__name__}: {e}")
        return result

    # Step 3: cost emission (per-invocation engine + direct INSERT)
    try:
        asyncio.run(_async_emit_cost(
            job_id=job_id,
            usage=_FakeUsage(),
            model="claude-haiku-stress",
            req_dict={
                "tenant_id": str(tenant_id),
                "caller_module": caller_module,
                "quality_tier": "standard",
            },
            service_type="prediction",
            task=task,
        ))
    except Exception as e:
        result["errors"].append(f"emit_cost: {e.__class__.__name__}: {e}")
        return result

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
          f"(mixed churn_prediction / revenue_forecast / "
          f"anomaly_detection / lead_scoring)\n")

    tasks = ["churn_prediction", "revenue_forecast",
             "anomaly_detection", "lead_scoring"]

    passed = 0
    for i in range(1, STRESS_COUNT + 1):
        task = tasks[i % len(tasks)]
        caller = "logicrm" if i % 3 == 0 else "crm"

        r = _run_one_iteration(i, tenant_id, caller, task)

        if r["ok"]:
            print(f"  [{i}/{STRESS_COUNT}] PASS  caller={caller:10s} "
                  f"task={task:20s} job_id={r['job_id']}")
            passed += 1
        else:
            print(f"  [{i}/{STRESS_COUNT}] FAIL  caller={caller:10s} "
                  f"task={task:20s}")
            for err in r["errors"]:
                print(f"          - {err}")
            print(f"\nSTOP-ON-FIRST-FAILURE. {passed}/{STRESS_COUNT} passed.")
            return 1

    print(f"\nRESULT: {passed}/{STRESS_COUNT} PASS")
    return 0 if passed == STRESS_COUNT else 1


if __name__ == "__main__":
    sys.exit(main())
