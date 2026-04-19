"""
ASP-10 Cost Aggregator

Runs as a Celery beat periodic task (monthly-cost-aggregation in
app.worker.celery_app.conf.beat_schedule — 01:00 UTC on the 1st of
each month). Manual invocation: `celery_app.send_task("asp.cost_aggregator")`.

MUST be idempotent — INSERT ... ON CONFLICT DO UPDATE.

**ASP-DEFECT-022 fix (2026-04-18 per ASP-OUT-022).** Previous implementation
used a synchronous `sqlalchemy.create_engine` with psycopg2 driver derived
from `settings.DATABASE_URL` by regex-stripping `+asyncpg`. psycopg2 was
NOT in `requirements.txt` — the Docker image has only asyncpg. The task
had never executed in pilot (the beat scheduler itself was inert until
I-RAG-04 added `-B`; when I-RAG-04 re-enabled beat, the aggregator's
first invocation failed with `No module named 'psycopg2'`).

v1.0 governed fix: use the existing async DB infrastructure
(`app.infra.db.get_session` → `AsyncSession` → asyncpg) and wrap the
async call inside the Celery task via `asyncio.run()`. Consistent with
the rest of the ASP stack — single Postgres driver.
"""
import asyncio
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

log = structlog.get_logger()


SQL = """
    INSERT INTO cost_monthly_reports
        (tenant_id, report_month, caller_module,
         total_calls, total_input_tokens, total_output_tokens, total_cost_usd)
    SELECT
        tenant_id,
        DATE_TRUNC('month', created_at)::date AS report_month,
        caller_module,
        COUNT(*) AS total_calls,
        SUM(input_tokens) AS total_input_tokens,
        SUM(output_tokens) AS total_output_tokens,
        SUM(cost_usd) AS total_cost_usd
    FROM cost_events
    WHERE DATE_TRUNC('month', created_at)::date = :report_month
      AND status = 'success'
    GROUP BY tenant_id, report_month, caller_module
    ON CONFLICT (tenant_id, report_month, caller_module)
    DO UPDATE SET
        total_calls         = EXCLUDED.total_calls,
        total_input_tokens  = EXCLUDED.total_input_tokens,
        total_output_tokens = EXCLUDED.total_output_tokens,
        total_cost_usd      = EXCLUDED.total_cost_usd,
        generated_at        = NOW()
"""


async def _do_aggregation(report_month) -> int:
    """Execute the monthly rollup. Returns affected row count (for tests).

    Creates a FRESH async engine scoped to this invocation. We cannot reuse
    the app-wide `app.infra.db` pool because Celery tasks use
    `asyncio.run()` — each invocation creates a new event loop, and
    asyncpg connections carry loop affinity. A pool created against loop A
    and reused from loop B fails with "got Future attached to a different
    loop". Scoped engine avoids the class of bug entirely; the small
    per-call connection cost is acceptable because this task fires at most
    monthly (or manually during ops).
    """
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(SQL), {"report_month": report_month})
            return result.rowcount if result.rowcount is not None else 0
    finally:
        await engine.dispose()


def register_task(celery_app):
    @celery_app.task(name="asp.cost_aggregator")
    def run_monthly_aggregation(year: int = None, month: int = None):
        """Aggregate cost_events → cost_monthly_reports for one month.

        If year/month not provided, aggregates the previous calendar month
        (the expected cron behaviour on the 1st of a month).

        Safe to re-run for the same month — INSERT ... ON CONFLICT DO UPDATE.
        """
        from datetime import date

        today = date.today()
        if not year:
            year = today.year
        if not month:
            # Previous calendar month
            if today.month == 1:
                month = 12
                year = today.year - 1
            else:
                month = today.month - 1

        report_month = date(year, month, 1)
        log.info("cost_aggregation_start", report_month=str(report_month))

        rowcount = asyncio.run(_do_aggregation(report_month))

        log.info(
            "cost_aggregation_complete",
            report_month=str(report_month),
            rows_affected=rowcount,
        )
        return {"report_month": str(report_month), "rows_affected": rowcount}

    return run_monthly_aggregation
