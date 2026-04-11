"""
Shared JSON extraction utility (ADR-025).

Three-pass resilient parser for LLM-generated JSON responses.
Used by ASP-01 NLP and ASP-03 Generation services.

Import: from app.utils.json_parser import extract_json
"""
import json
import re

import structlog

log = structlog.get_logger()


class LLMParseError(Exception):
    """Raised when all JSON extraction attempts fail."""
    pass


def extract_json(raw_text: str) -> dict:
    """Extract JSON dict from LLM output with 3-pass resilience.

    Pass 1: Direct json.loads()
    Pass 2: Strip markdown fences (```json ... ```) then json.loads()
    Pass 3: Find first '{' to last '}' substring then json.loads()

    Raises:
        LLMParseError: If all extraction attempts fail.
    """
    text = raw_text.strip()

    # Pass 1: Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Pass 2: Strip markdown fences
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", text)
    stripped = re.sub(r"\n?\s*```\s*$", "", stripped).strip()
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Pass 3: Extract first { ... last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        substring = text[first_brace:last_brace + 1]
        try:
            result = json.loads(substring)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    raise LLMParseError(
        f"Failed to extract JSON from LLM response. "
        f"Raw text (first 200 chars): {raw_text[:200]}"
    )
