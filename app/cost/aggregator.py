"""
ASP-10 Cost Aggregator

Runs as a Celery beat periodic task locally.
In production: AWS Lambda on EventBridge monthly rule.

MUST be idempotent — INSERT ... ON CONFLICT DO UPDATE.
"""
import structlog
from sqlalchemy import text

log = structlog.get_logger()


def register_task(celery_app):
    @celery_app.task(name="asp.cost_aggregator")
    def run_monthly_aggregation(year: int = None, month: int = None):
        """
        If year/month not provided, aggregates for the previous calendar month.
        Writes to cost_monthly_reports. Safe to re-run.
        """
        from datetime import date
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.config import settings
        import re

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

        sync_url = re.sub(r"postgresql\+asyncpg", "postgresql", settings.DATABASE_URL)
        engine = create_engine(sync_url)
        Session = sessionmaker(bind=engine)

        sql = """
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

        with Session() as session:
            session.execute(text(sql), {"report_month": report_month})
            session.commit()

        log.info("cost_aggregation_complete", report_month=str(report_month))

    return run_monthly_aggregation
