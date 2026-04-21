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

    # ASP-FEAT-ASP-04 v1.0 §6.1 / OQ-2 (ASP-OUT-055 correction).
    # Max PDF upload size in MB. 10 MB governs (spec §6.1 text had 20 MB
    # as the Batch 2 placeholder; OQ-2 ruling set 10 MB as the final v1.0
    # value). Invoice PDFs are typically <2 MB; 10 MB gives adequate
    # headroom with lower attack surface.
    ASP_DOC_UPLOAD_MAX_MB: int = 10

    # App
    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "INFO"
    API_KEY_HEADER: str = "X-ASP-API-Key"

    # Context store TTL
    CONTEXT_TTL_SECONDS: int = 3600

    # ChromaDB persistence (ASP-02 RAG — I-RAG-01)
    # Switched from chromadb.Client() (ephemeral) to PersistentClient(path=...)
    # on 2026-04-18. The ephemeral client meant nl_to_sql retrieval has never
    # survived a container restart; coupled with the ONNX model cache miss
    # (no model.onnx ever downloaded), the capability had never executed
    # successfully in any pilot environment. Path is a named Docker volume
    # shared between ai-service and celery-worker so the Ontology Manager
    # (Celery) and RAG read path (FastAPI) see the same collections.
    CHROMA_PERSIST_PATH: str = "/chroma/data"

    # RAG embedding model (ASP-02 — I-RAG-02, Architect 20:10 IST Option C).
    # Explicit binding replaces ChromaDB's ONNXMiniLM_L6_V2 default. The model
    # is pre-downloaded into the container image at build time (see Dockerfile
    # `sentence-transformers preload` step) so first-request latency is zero
    # and no runtime network fetch is ever required. Collection metadata
    # snapshots this value as `asp_embedding_model` for drift detection.
    RAG_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Chroma client singleton TTL (ASP-02 — I-RAG-02, OQ-RAG-CACHE-01 Option B).
    # The ai-service `_chroma_client` singleton caches the collection registry
    # in-memory. After this many seconds, the next `get_chroma_client()` call
    # re-initialises the client so cross-process writes (from Ontology Manager
    # in celery-worker) become visible without requiring an ai-service restart.
    # Pilot default: 5 minutes.
    CHROMA_CLIENT_TTL_SECONDS: int = 300

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
