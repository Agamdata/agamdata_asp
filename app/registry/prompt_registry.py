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
from sqlalchemy import select, text

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
    """Fetch prompt by exact ab_variant, with (caller, maturity) fallback chain.

    Resolution order (most specific → least specific):
      1. (caller_module, maturity_level)
      2. (caller_module, '*')
      3. ('*',           maturity_level)
      4. ('*',           '*')

    Loud-failure semantics apply to **ab_variant** only. An unknown
    ab_variant (e.g. a typo, or a new variant not yet seeded) must fail
    with PromptNotFoundError — we do NOT fall back across variants
    because doing so risks returning the wrong language/shape
    (e.g. TypeScript when Python was requested).

    The 4-level (caller × maturity) fallback for the MATCHING ab_variant
    is safe and mirrors `get_prompt()` semantics. Added in v2.0
    (ASP-OUT-014, 2026-04-18) to resolve a migration-024 regression:
    v4 rows are at maturity_level='*' but callers arrive with Literal
    maturity L0..L3; without the chain, exact-match never succeeds.

    Cache key includes the requested (caller, maturity, variant) tuple
    so lookups with different inputs don't collide on the same cache
    entry even when they resolve to the same row.
    """
    cache_key = f"prompt:{service_type}:{task}:{caller_module}:{maturity_level}:{ab_variant}"
    redis = get_redis()

    cached = await redis.get(cache_key)
    if cached:
        return PromptTemplateDTO.model_validate_json(cached)

    # Priority-ordered fallback: most specific row first, then progressively
    # wider wildcards on (caller_module, maturity_level). ab_variant is EXACT.
    # CASE expression encodes the fallback priority; LIMIT 1 returns the
    # winning row. If nothing matches any of the 4 shapes, the query returns
    # zero rows and we raise PromptNotFoundError.
    fallback_sql = text("""
        SELECT id, service_type, task, caller_module, maturity_level, version,
               is_active, system_prompt, user_prompt_template, ab_variant
        FROM prompt_templates
        WHERE service_type = :service_type
          AND task = :task
          AND ab_variant = :ab_variant
          AND is_active = TRUE
          AND (
            (caller_module = :caller AND maturity_level = :maturity)
            OR (caller_module = :caller AND maturity_level = '*')
            OR (caller_module = '*'    AND maturity_level = :maturity)
            OR (caller_module = '*'    AND maturity_level = '*')
          )
        ORDER BY
          CASE
            WHEN caller_module = :caller AND maturity_level = :maturity THEN 0
            WHEN caller_module = :caller AND maturity_level = '*'       THEN 1
            WHEN caller_module = '*'    AND maturity_level = :maturity  THEN 2
            ELSE 3
          END,
          version DESC
        LIMIT 1
    """)

    async with get_session() as session:
        result = await session.execute(
            fallback_sql,
            {
                "service_type": service_type,
                "task": task,
                "ab_variant": ab_variant,
                "caller": caller_module,
                "maturity": maturity_level,
            },
        )
        row = result.mappings().first()

    if row:
        dto = PromptTemplateDTO(
            id=str(row["id"]),
            service_type=row["service_type"],
            task=row["task"],
            caller_module=row["caller_module"],
            maturity_level=row["maturity_level"],
            version=row["version"],
            system_prompt=row["system_prompt"],
            user_prompt_template=row["user_prompt_template"],
            ab_variant=row["ab_variant"],
        )
        await redis.setex(cache_key, 600, dto.model_dump_json())
        return dto

    # ab_variant is unknown OR no row exists at any (caller, maturity) level.
    # This is the correct loud failure — the caller asked for a variant
    # that is not seeded. Surface the exact requested tuple so the operator
    # can diagnose.
    raise PromptNotFoundError(
        f"No prompt for {service_type}/{task}/{caller_module}/{maturity_level}"
        f" with variant '{ab_variant}' (no match at any of the 4 fallback levels)"
    )
