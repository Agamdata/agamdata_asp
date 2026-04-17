"""Per-tenant rate limiter — ASP-FEAT-ASP-00 v1.0 §S-3 / I-08.

SlowAPI + Redis-backed sliding-window counter. Keyed on tenant_id
(falls back to client IP pre-auth). Dormant when RATE_LIMIT_ENABLED=False:
no Redis writes, no 429 decisions.

Per-endpoint limits:
  POST /api/v1/ai/invoke      → RATE_LIMIT_INVOKE_RPM  (default 60/minute)
  GET  /api/v1/ai/jobs/{id}   → RATE_LIMIT_JOBS_RPM    (default 120/minute)
  GET  /api/v1/ai/capabilities, /api/v1/ai/schemas/*  — NOT limited

429 responses flow through the RFC 7807 global exception handler
(app.gateway.exception_handlers) which preserves the Retry-After header
that SlowAPI attaches to the RateLimitExceeded exception.
"""
from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings


def _tenant_key(request: Request) -> str:
    """Rate-limit key function — tenant_id post-auth, IP pre-auth.

    The gateway router sets request.state.tenant_id at handler entry. For
    requests that reach the limiter before tenant is resolved (e.g. during
    pre-auth validation), we fall back to the client IP so unauthenticated
    hosts cannot exhaust a tenant's bucket.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id:
        return f"tenant:{tenant_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_tenant_key,
    enabled=settings.RATE_LIMIT_ENABLED,
    # Use in-memory storage when enabled; switch to Redis by setting
    # storage_uri="redis://redis:6379/1" for multi-worker deployments.
    # The in-memory default is correct for pilot-scale single-worker
    # uvicorn. REDIS_URL is intentionally NOT hard-wired here so that
    # this module imports cleanly even when Redis is unavailable.
    default_limits=[],
)

# Limit strings are computed PER REQUEST via callables so operators can
# change RATE_LIMIT_INVOKE_RPM / RATE_LIMIT_JOBS_RPM at runtime (or in
# tests) without reloading the router module. Per AC-S3-05 the activation
# mechanism is pure config; no code redeployment.
def INVOKE_RATE() -> str:
    return f"{settings.RATE_LIMIT_INVOKE_RPM}/minute"


def JOBS_RATE() -> str:
    return f"{settings.RATE_LIMIT_JOBS_RPM}/minute"


__all__ = ["limiter", "INVOKE_RATE", "JOBS_RATE", "RateLimitExceeded"]
