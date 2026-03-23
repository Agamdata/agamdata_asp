"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-21 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("monthly_quota_usd", sa.Numeric(10, 4), nullable=False, server_default="50.0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_code"),
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_type", sa.String(64), nullable=False),
        sa.Column("task", sa.String(128), nullable=False),
        sa.Column("caller_module", sa.String(64), nullable=False),
        sa.Column("maturity_level", sa.String(8), nullable=False, server_default="*"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("user_prompt_template", sa.Text, nullable=False),
        sa.Column("ab_variant", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint(
            "service_type", "task", "caller_module", "maturity_level", "version", "ab_variant",
            name="uq_prompt_lookup",
        ),
    )
    op.create_index(
        "idx_prompt_lookup",
        "prompt_templates",
        ["service_type", "task", "caller_module", "maturity_level", "is_active"],
    )

    op.create_table(
        "cost_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("caller_module", sa.String(64), nullable=False),
        sa.Column("service_type", sa.String(64), nullable=False),
        sa.Column("task", sa.String(128), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("quality_tier", sa.String(32), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_cost_tenant_month", "cost_events", ["tenant_id", "created_at"])
    op.create_index("idx_cost_module", "cost_events", ["caller_module", "created_at"])

    op.create_table(
        "cost_monthly_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("report_month", sa.Date, nullable=False),
        sa.Column("caller_module", sa.String(64), nullable=False),
        sa.Column("total_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_input_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "report_month", "caller_module", name="uq_monthly_report"),
    )

    op.create_table(
        "async_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", sa.String(128), nullable=False, unique=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("caller_module", sa.String(64), nullable=False),
        sa.Column("service_type", sa.String(64), nullable=False),
        sa.Column("task", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("result_json", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("webhook_url", sa.String(512), nullable=True),
        sa.Column("webhook_delivered", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("webhook_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_jobs_tenant", "async_jobs", ["tenant_id", "created_at"])

    op.create_table(
        "webhook_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("caller_module", sa.String(64), nullable=False),
        sa.Column("callback_url", sa.String(512), nullable=False),
        sa.Column("secret_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "caller_module", name="uq_webhook_tenant_module"),
    )


def downgrade() -> None:
    op.drop_table("webhook_registrations")
    op.drop_table("async_jobs")
    op.drop_table("cost_monthly_reports")
    op.drop_table("cost_events")
    op.drop_index("idx_prompt_lookup", table_name="prompt_templates")
    op.drop_table("prompt_templates")
    op.drop_table("tenants")
