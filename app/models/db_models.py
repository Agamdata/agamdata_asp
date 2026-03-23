import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, BigInteger, Column, Date, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint, Index,
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
    api_key_hash = Column(String(255), nullable=False)
    monthly_quota_usd = Column(Numeric(10, 4), nullable=False, default=50.0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    cost_events = relationship("CostEvent", back_populates="tenant")
    async_jobs = relationship("AsyncJob", back_populates="tenant")
    webhook_registrations = relationship("WebhookRegistration", back_populates="tenant")
    monthly_reports = relationship("CostMonthlyReport", back_populates="tenant")


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
