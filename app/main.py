from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import HTTPException

from app.config import configure_logging
from app.infra.db import init_db
from app.infra.redis import init_redis
from app.gateway.router import router as gateway_router
from app.gateway.exception_handlers import http_exception_handler
from app.gateway.middleware.rate_limiter import limiter
from slowapi.errors import RateLimitExceeded
from app.cost.meter import router as cost_router
from app.webhook.service import router as webhook_router
from app.api.capabilities import router as capabilities_router
from app.api.documents import router as documents_router  # I-DOC-05

configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    log.info("ASP startup complete")
    yield
    log.info("ASP shutdown")


app = FastAPI(
    title="AI Services Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(gateway_router, prefix="/api/v1")
app.include_router(cost_router, prefix="/api/v1/cost")
app.include_router(webhook_router, prefix="/api/v1/webhooks")
app.include_router(capabilities_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")  # I-DOC-05

# RFC 7807 global exception handler — renders problem+json envelope at top level.
# Per ASP-FEAT-ASP-00 v1.0 §11 I-RFC7807.
app.add_exception_handler(HTTPException, http_exception_handler)


# I-08 — Rate limiter wiring.
# Attach limiter to app so slowapi middleware can find it via app.state.limiter.
# Translate RateLimitExceeded -> HTTPException(429) so the RFC 7807 handler
# renders the problem+json envelope. Retry-After header is extracted from the
# SlowAPI exception and forwarded.
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_exceeded_handler(request, exc: RateLimitExceeded):
    # SlowAPI stores the human-readable limit string on exc.detail
    # (e.g. "5 per 1 minute") and the retry window in exc.limit.
    retry_after_s = 60  # conservative default — one full minute bucket
    try:
        reset = getattr(exc, "limit", None)
        if reset is not None and hasattr(reset, "limit"):
            # limits.RateLimitItem carries a GRANULARITY that maps to seconds
            retry_after_s = int(reset.limit.GRANULARITY.seconds)
    except Exception:
        pass

    http_exc = HTTPException(
        status_code=429,
        detail=f"Rate limit exceeded: {exc.detail}" if getattr(exc, "detail", None) else "Rate limit exceeded",
        headers={"Retry-After": str(retry_after_s)},
    )
    return await http_exception_handler(request, http_exc)


# I-13 — X-Request-Id response header (pure ASGI middleware).
# Pulls request.state.request_id on its way out and stamps it on the
# response headers. A pure ASGI middleware is used (rather than
# @app.middleware("http") which wraps BaseHTTPMiddleware) because
# BaseHTTPMiddleware spawns a task on a different event loop than the
# request handler, which breaks asyncpg connection pools shared across
# the request lifecycle.
class RequestIdHeaderMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                rid = scope.get("state", {}).get("request_id") if isinstance(scope.get("state"), dict) else None
                # Starlette stores request.state on scope["state"] as an object;
                # .request_id is an attribute. Handle both shapes.
                if rid is None:
                    state_obj = scope.get("state")
                    if state_obj is not None and hasattr(state_obj, "request_id"):
                        rid = state_obj.request_id
                if rid:
                    headers = list(message.get("headers", []))
                    headers.append((b"x-request-id", str(rid).encode("latin-1")))
                    message = dict(message)
                    message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_header)


app.add_middleware(RequestIdHeaderMiddleware)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
