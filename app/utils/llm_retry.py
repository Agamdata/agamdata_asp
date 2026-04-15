"""
Shared LLM retry utility — handles Anthropic 529 (Overloaded) with exponential backoff.

ASP-DEFECT-016: Anthropic 529 responses were surfaced as unhandled 500 to callers.
Correct behavior: retry with backoff, then return 502 if exhausted.

Usage:
    from app.utils.llm_retry import llm_call_with_retry

    response = await llm_call_with_retry(
        anthropic_client, model=model, max_tokens=8192,
        system=system_prompt, messages=messages,
        request_id=request_id,
    )

All LLM-calling services should use this instead of calling anthropic_client directly.
Atrium-transition relevance: REPLICATE — platform-level concern, not per-service.
"""
import asyncio

import structlog
from anthropic import APIStatusError
from fastapi import HTTPException

log = structlog.get_logger()

# Retry configuration
MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]  # exponential: 1s, 2s, 4s

# Retryable status codes from Anthropic
RETRYABLE_STATUS_CODES = {529, 500, 502, 503, 504}


async def llm_call_with_retry(
    client,
    *,
    model: str,
    max_tokens: int,
    system: str,
    messages: list[dict],
    request_id: str = "",
) -> object:
    """Call Anthropic API with retry logic for transient errors.

    Retries on: 529 (Overloaded), 500, 502, 503, 504, and connection errors.
    Does NOT retry on: 400, 401, 403, 404, 422 (non-retryable).

    On all retries exhausted: raises HTTPException(502) with RFC 7807 detail.
    """
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return response

        except APIStatusError as e:
            last_error = e
            status = e.status_code

            if status not in RETRYABLE_STATUS_CODES:
                # Non-retryable (400, 401, 422, etc.) — fail immediately
                log.error(
                    "llm_call_non_retryable",
                    request_id=request_id,
                    status=status,
                    error=str(e),
                )
                raise

            if attempt < MAX_RETRIES:
                delay = BACKOFF_SECONDS[attempt]
                log.warning(
                    "llm_overloaded",
                    request_id=request_id,
                    attempt=attempt + 1,
                    max_retries=MAX_RETRIES,
                    status=status,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
            else:
                log.error(
                    "llm_retries_exhausted",
                    request_id=request_id,
                    attempts=MAX_RETRIES + 1,
                    last_status=status,
                )

        except (ConnectionError, TimeoutError, OSError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = BACKOFF_SECONDS[attempt]
                log.warning(
                    "llm_connection_error",
                    request_id=request_id,
                    attempt=attempt + 1,
                    error=str(e),
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
            else:
                log.error(
                    "llm_retries_exhausted",
                    request_id=request_id,
                    attempts=MAX_RETRIES + 1,
                    error=str(e),
                )

    # All retries exhausted — return 502 per ADR-011
    raise HTTPException(
        status_code=502,
        detail={
            "detail": "Upstream LLM provider temporarily unavailable. Retry after a short delay.",
            "request_id": request_id,
        },
    )
