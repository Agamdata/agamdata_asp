"""
ASP-07 Context Store

Redis key: ctx:{tenant_id}:{caller_module}:{session_id}
TTL: CONTEXT_TTL_SECONDS from config (default 3600)
Value: JSON list of ConversationTurn objects
"""
import json

from app.config import settings
from app.infra.redis import get_redis
from app.models.request import ConversationTurn


async def get_context(
    tenant_id: str,
    caller_module: str,
    session_id: str,
) -> list[ConversationTurn]:
    key = f"ctx:{tenant_id}:{caller_module}:{session_id}"
    redis = get_redis()
    raw = await redis.get(key)
    if not raw:
        return []
    return [ConversationTurn.model_validate(t) for t in json.loads(raw)]


async def set_context(
    tenant_id: str,
    caller_module: str,
    session_id: str,
    turns: list[ConversationTurn],
) -> None:
    key = f"ctx:{tenant_id}:{caller_module}:{session_id}"
    redis = get_redis()
    await redis.setex(
        key,
        settings.CONTEXT_TTL_SECONDS,
        json.dumps([t.model_dump() for t in turns]),
    )


async def delete_context(
    tenant_id: str,
    caller_module: str,
    session_id: str,
) -> None:
    key = f"ctx:{tenant_id}:{caller_module}:{session_id}"
    redis = get_redis()
    await redis.delete(key)
