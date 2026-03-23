"""
ASP-06 Prompt Registry

Lookup order: exact match (module+maturity) -> module wildcard -> full wildcard
Redis cache key: prompt:{service_type}:{task}:{caller_module}:{maturity_level}
Cache TTL: 600 seconds (10 minutes)
"""
import json
from typing import Optional

import structlog
from pydantic import BaseModel
from sqlalchemy import select

from app.infra.db import get_session
from app.infra.redis import get_redis
from app.models.db_models import PromptTemplate

log = structlog.get_logger()


class PromptNotFoundError(Exception):
    pass


class PromptTemplateDTO(BaseModel):
    id: str
    service_type: str
    task: str
    caller_module: str
    maturity_level: str
    version: int
    system_prompt: str
    user_prompt_template: str
    ab_variant: Optional[str] = None


async def get_prompt(
    service_type: str,
    task: str,
    caller_module: str,
    maturity_level: str,
) -> PromptTemplateDTO:
    cache_key = f"prompt:{service_type}:{task}:{caller_module}:{maturity_level}"
    redis = get_redis()

    cached = await redis.get(cache_key)
    if cached:
        return PromptTemplateDTO.model_validate_json(cached)

    # Fallback chain: exact -> module wildcard -> maturity wildcard -> full wildcard
    async with get_session() as session:
        for mod, mat in [
            (caller_module, maturity_level),
            (caller_module, "*"),
            ("*", maturity_level),
            ("*", "*"),
        ]:
            result = await session.execute(
                select(PromptTemplate).where(
                    PromptTemplate.service_type == service_type,
                    PromptTemplate.task == task,
                    PromptTemplate.caller_module == mod,
                    PromptTemplate.maturity_level == mat,
                    PromptTemplate.is_active == True,
                ).order_by(PromptTemplate.version.desc()).limit(1)
            )
            row = result.scalar_one_or_none()
            if row:
                dto = PromptTemplateDTO(
                    id=str(row.id),
                    service_type=row.service_type,
                    task=row.task,
                    caller_module=row.caller_module,
                    maturity_level=row.maturity_level,
                    version=row.version,
                    system_prompt=row.system_prompt,
                    user_prompt_template=row.user_prompt_template,
                    ab_variant=row.ab_variant,
                )
                await redis.setex(cache_key, 600, dto.model_dump_json())
                return dto

    raise PromptNotFoundError(
        f"No prompt for {service_type}/{task}/{caller_module}/{maturity_level}"
    )


async def get_prompt_variant(
    service_type: str,
    task: str,
    caller_module: str,
    maturity_level: str,
    ab_variant: str,
) -> PromptTemplateDTO:
    """
    Fetch prompt by exact ab_variant.
    Cache key includes variant to prevent collision with default prompt.
    Falls back to get_prompt() if exact variant not found.
    """
    cache_key = f"prompt:{service_type}:{task}:{caller_module}:{maturity_level}:{ab_variant}"
    redis = get_redis()

    cached = await redis.get(cache_key)
    if cached:
        return PromptTemplateDTO.model_validate_json(cached)

    async with get_session() as session:
        result = await session.execute(
            select(PromptTemplate).where(
                PromptTemplate.service_type == service_type,
                PromptTemplate.task == task,
                PromptTemplate.caller_module == caller_module,
                PromptTemplate.maturity_level == maturity_level,
                PromptTemplate.ab_variant == ab_variant,
                PromptTemplate.is_active == True,
            ).order_by(PromptTemplate.version.desc()).limit(1)
        )
        row = result.scalar_one_or_none()

    if row:
        dto = PromptTemplateDTO(
            id=str(row.id),
            service_type=row.service_type,
            task=row.task,
            caller_module=row.caller_module,
            maturity_level=row.maturity_level,
            version=row.version,
            system_prompt=row.system_prompt,
            user_prompt_template=row.user_prompt_template,
            ab_variant=row.ab_variant,
        )
        await redis.setex(cache_key, 600, dto.model_dump_json())
        return dto

    # No silent fallback — an unknown variant must fail loudly.
    # Falling back to get_prompt() would silently return the wrong language
    # (e.g. TypeScript when Python was requested) and poison the Redis cache
    # for the non-variant key, causing every subsequent retry to fail.
    raise PromptNotFoundError(
        f"No prompt for {service_type}/{task}/{caller_module}/{maturity_level}"
        f" with variant '{ab_variant}'"
    )
