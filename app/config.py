import logging
from pydantic_settings import BaseSettings
import structlog


class Settings(BaseSettings):
    # LLM
    ANTHROPIC_API_KEY: str

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Object storage
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_DOCS: str = "asp-documents"

    # App
    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "INFO"
    API_KEY_HEADER: str = "X-ASP-API-Key"

    # Context store TTL
    CONTEXT_TTL_SECONDS: int = 3600

    # Model routing
    MODEL_STANDARD: str = "claude-haiku-4-5-20251001"
    MODEL_ENHANCED: str = "claude-sonnet-4-5-20251001"
    MODEL_PREMIUM: str = "claude-opus-4-5-20251001"

    # Cost quota
    DEFAULT_MONTHLY_QUOTA_USD: float = 50.0

    # Webhook
    WEBHOOK_MAX_RETRIES: int = 5
    WEBHOOK_RETRY_DELAY_SECONDS: int = 30

    # Rate limiting (ASP-FEAT-ASP-00 v1.0 §S-3, I-08)
    # Per-tenant rate limits. Dormant by default; operator enables via env only.
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_INVOKE_RPM: int = 60
    RATE_LIMIT_JOBS_RPM: int = 120

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        ),
    )
