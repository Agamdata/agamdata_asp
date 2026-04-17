from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import HTTPException

from app.config import configure_logging
from app.infra.db import init_db
from app.infra.redis import init_redis
from app.gateway.router import router as gateway_router
from app.gateway.exception_handlers import http_exception_handler
from app.cost.meter import router as cost_router
from app.webhook.service import router as webhook_router
from app.api.capabilities import router as capabilities_router

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

# RFC 7807 global exception handler — renders problem+json envelope at top level.
# Per ASP-FEAT-ASP-00 v1.0 §11 I-RFC7807.
app.add_exception_handler(HTTPException, http_exception_handler)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
