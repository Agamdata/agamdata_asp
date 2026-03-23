"""FastAPI dependency injectors."""
from app.infra.db import get_db
from app.infra.redis import get_redis

__all__ = ["get_db", "get_redis"]
