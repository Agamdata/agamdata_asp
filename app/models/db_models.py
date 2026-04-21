import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, BigInteger, CheckConstraint, Column, Date, DateTime,
    Float, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, Index, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_code = Column(String(64), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    # api_key_hash dropped in migration 023. Authoritative source is
    # tenant_api_keys (junction). See ASP-FEAT-ASP-00 v1.0 §5.
    monthly_quota_usd = Column(Numeric(10, 4), nullable=False, default=50.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    api_keys = relationship(
        "TenantApiKey", back_populates="tenant", cascade="all, delete-orphan",
    )
    cost_events = relationship("CostEvent", back_populates="tenant")
    async_jobs = relationship("AsyncJob", back_populates="tenant")
    webhook_registrations = relationship("WebhookRegistration", back_populates="tenant")
    monthly_reports = relationship("CostMonthlyReport", back_populates="tenant")
    # ASP-FEAT-ASP-04 v1.0 §5.6 — cascade delete-orphan matches api_keys
    # pattern (tenant purge removes registry rows atomically; DB-level
    # CASCADE in migration 0029 is the ultimate guard).
    documents = relationship(
        "Document", back_populates="tenant", cascade="all, delete-orphan",
    )


class TenantApiKey(Base):
    """Multi-key junction per tenant — ASP-FEAT-ASP-00 v1.0 §5 (ADR-032 mechanics).

    Replaces the single tenants.api_key_hash column (dropped in migration 023).
    Supports rotation with overlap windows, revocation audit, optional expiry,
    operator-facing labels.

    Legacy rows (backfilled in migration 023) have key_prefix starting 'leg_'.
    New-format rows have key_prefix matching r'^[a-z0-9]{12}$' (no underscore,
    by construction — see app.utils.key_generator).

    Invariants enforced by DB CHECK constraints:
      - ck_tenant_api_keys_revocation_consistency:
          is_active=FALSE ⇔ revoked_at IS NOT NULL
      - ck_tenant_api_keys_expiry_order:
          expires_at IS NULL OR expires_at > issued_at
    """

    __tablename__ = "tenant_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_prefix = Column(String(12), nullable=False, unique=True, index=True)
    api_key_hash = Column(String(255), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    label = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow,
    )

    tenant = relationship("Tenant", back_populates="api_keys")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_type = Column(String(64), nullable=False)
    task = Column(String(128), nullable=False)
    caller_module = Column(String(64), nullable=False)
    maturity_level = Column(String(8), nullable=False, default="*")
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=False)
    ab_variant = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "service_type", "task", "caller_module", "maturity_level", "version", "ab_variant",
            name="uq_prompt_lookup",
        ),
        Index("idx_prompt_lookup", "service_type", "task", "caller_module", "maturity_level", "is_active"),
    )


class CostEvent(Base):
    __tablename__ = "cost_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    caller_module = Column(String(64), nullable=False)
    service_type = Column(String(64), nullable=False)
    task = Column(String(128), nullable=False)
    model = Column(String(128), nullable=False)
    quality_tier = Column(String(32), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(12, 8), nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    # F-01-10 governance — ASP-FEAT-ASP-00 v1.0 §5 / §7.
    # NULL means pre-feature row or non-PAP caller. NOT a data-quality issue.
    caller_feature = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    tenant = relationship("Tenant", back_populates="cost_events")

    __table_args__ = (
        Index("idx_cost_tenant_month", "tenant_id", "created_at"),
        Index("idx_cost_module", "caller_module", "created_at"),
    )


class CostMonthlyReport(Base):
    __tablename__ = "cost_monthly_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    report_month = Column(Date, nullable=False)
    caller_module = Column(String(64), nullable=False)
    total_calls = Column(Integer, nullable=False, default=0)
    total_input_tokens = Column(BigInteger, nullable=False, default=0)
    total_output_tokens = Column(BigInteger, nullable=False, default=0)
    total_cost_usd = Column(Numeric(12, 4), nullable=False, default=0)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    tenant = relationship("Tenant", back_populates="monthly_reports")

    __table_args__ = (
        UniqueConstraint("tenant_id", "report_month", "caller_module", name="uq_monthly_report"),
    )


class AsyncJob(Base):
    __tablename__ = "async_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(128), nullable=False, unique=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    caller_module = Column(String(64), nullable=False)
    service_type = Column(String(64), nullable=False)
    task = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    result_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    webhook_url = Column(String(512), nullable=True)
    webhook_delivered = Column(Boolean, nullable=False, default=False)
    webhook_attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="async_jobs")

    __table_args__ = (
        Index("idx_jobs_tenant", "tenant_id", "created_at"),
    )


class WebhookRegistration(Base):
    __tablename__ = "webhook_registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    caller_module = Column(String(64), nullable=False)
    callback_url = Column(String(512), nullable=False)
    secret_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    tenant = relationship("Tenant", back_populates="webhook_registrations")

    __table_args__ = (
        UniqueConstraint("tenant_id", "caller_module", name="uq_webhook_tenant_module"),
    )


# ─────────────────────────────────────────────────────────────────────
# ASP-FEAT-ASP-04 v1.0 §5.6 — documents registry (migration 0029).
# ─────────────────────────────────────────────────────────────────────

class Document(Base):
    """Tracked-document registry for the ASP-04 Doc Intelligence demo
    flow. One row per uploaded PDF; carries classification +
    extraction state transitions and the final extracted fields
    JSONB. See ASP-FEAT-ASP-04 v1.0 §5.1 for the governed column
    contract."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename = Column(String(255), nullable=False)
    storage_path      = Column(String(512), nullable=False)
    document_type     = Column(String(64),  nullable=True)
    classification_confidence = Column(Float, nullable=True)
    extraction_status = Column(String(32),  nullable=False, default="pending")
    extraction_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("async_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    extracted_fields  = Column(JSONB, nullable=True)
    uploaded_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow,
    )
    updated_at  = Column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        onupdate=utcnow,
    )

    tenant = relationship("Tenant", back_populates="documents")

    __table_args__ = (
        CheckConstraint(
            "extraction_status IN ('pending','classifying','extracting',"
            "'complete','failed')",
            name="ck_documents_extraction_status",
        ),
        Index(
            "ix_documents_tenant_uploaded",
            "tenant_id", text("uploaded_at DESC"),
        ),
        # Partial index in migration 0029 is not replicated here —
        # Alembic owns the WHERE clause; ORM metadata is for
        # querying, not re-issuing DDL.
    )
