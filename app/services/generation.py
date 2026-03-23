"""
ASP-03 Generation Service

Supported tasks:
- draft_email
- summarise_customer
- generate_quote_narrative
- suggest_fields
- draft_whatsapp
- generate_test_cases          (NEW)
- generate_playwright_script   (NEW)
"""
import json
import structlog
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any

from app.models.request import InvokeRequest, GenerateTestCasesPayload, GeneratePlaywrightScriptPayload
from app.models.response import InvokeResponse
from app.models.generation_schemas import GenerateTestCasesOutput, GeneratePlaywrightScriptOutput
from app.registry import prompt_registry
from app.services._shared import anthropic_client, build_invoke_response, strip_json, strip_script, repair_json

log = structlog.get_logger()


# ── Existing output schemas ───────────────────────────────────────────────────

class DraftEmailOutput(BaseModel):
    subject: str
    body: str
    word_count: int


class SummariseCustomerOutput(BaseModel):
    summary: str
    key_facts: list[str]
    risk_flags: list[str]


class GenerateQuoteNarrativeOutput(BaseModel):
    narrative: str


class SuggestFieldsOutput(BaseModel):
    suggestions: dict[str, Any]


class DraftWhatsappOutput(BaseModel):
    message: str
    char_count: int


# ── Task registry ─────────────────────────────────────────────────────────────

VALID_TASKS = {
    "draft_email",
    "summarise_customer",
    "generate_quote_narrative",
    "suggest_fields",
    "draft_whatsapp",
    "generate_test_cases",          # NEW
    "generate_playwright_script",   # NEW
}

TASK_OUTPUT_SCHEMAS = {
    "draft_email":                DraftEmailOutput,
    "summarise_customer":         SummariseCustomerOutput,
    "generate_quote_narrative":   GenerateQuoteNarrativeOutput,
    "suggest_fields":             SuggestFieldsOutput,
    "draft_whatsapp":             DraftWhatsappOutput,
    "generate_test_cases":        GenerateTestCasesOutput,        # NEW
    "generate_playwright_script": GeneratePlaywrightScriptOutput, # NEW
}

TASK_PAYLOAD_VALIDATORS = {
    "generate_test_cases":        GenerateTestCasesPayload,
    "generate_playwright_script": GeneratePlaywrightScriptPayload,
}

TASK_MAX_TOKENS = {
    "draft_email":                1024,
    "summarise_customer":         1024,
    "generate_quote_narrative":   1024,
    "suggest_fields":             512,
    "draft_whatsapp":             512,
    "generate_test_cases":        32000,  # large — 6-10 test cases with full locators/steps
    "generate_playwright_script": 32000,  # large — full TS file
}


# ── Main handler ──────────────────────────────────────────────────────────────

async def handle(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    task = req.task
    if task not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown generation task: {task}")

    log.info("generation_invoke_start", request_id=request_id, tenant_id=req.tenant_id,
             caller_module=req.caller_module, task=task, model=model)

    maturity = req.user_context.maturity_level if req.user_context else "L2"

    # Validate payload for tasks that have validators
    validated_payload = req.payload
    if task in TASK_PAYLOAD_VALIDATORS:
        try:
            validated = TASK_PAYLOAD_VALIDATORS[task](**req.payload)
            validated_payload = validated.model_dump()
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid payload for task {task}: {e}")

    # Fetch prompt — variant-aware for test automation tasks
    if task in ("generate_test_cases", "generate_playwright_script"):
        if task == "generate_test_cases":
            variant = validated_payload.get("locator_source", "inferred")
        else:
            variant = validated_payload.get("script_variant", "playwright_typescript_pom")
        prompt = await prompt_registry.get_prompt_variant(
            service_type="generation",
            task=task,
            caller_module=req.caller_module,
            maturity_level=maturity,
            ab_variant=variant,
        )
    else:
        prompt = await prompt_registry.get_prompt("generation", task, req.caller_module, maturity)

    # Build user message
    if task == "generate_test_cases":
        user_message = _build_test_cases_message(validated_payload, prompt)
    elif task == "generate_playwright_script":
        user_message = _build_script_message(validated_payload, prompt)
    else:
        try:
            user_message = prompt.user_prompt_template.format(**validated_payload)
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required payload field: {e}")

    max_tokens = TASK_MAX_TOKENS.get(task, 2048)
    response = await anthropic_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=prompt.system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = response.content[0].text

    # generate_playwright_script returns raw code — strip fences/labels, wrap directly
    if task == "generate_playwright_script":
        from app.models.generation_schemas import GeneratePlaywrightScriptOutput
        output = GeneratePlaywrightScriptOutput(script=strip_script(raw))
    else:
        schema_cls = TASK_OUTPUT_SCHEMAS[task]
        try:
            output = schema_cls.model_validate_json(strip_json(raw))
        except Exception as first_err:
            # Fallback: repair invalid escapes + truncation then retry
            try:
                output = schema_cls.model_validate_json(repair_json(raw))
                log.warning("generation_parse_repaired", request_id=request_id, task=task)
            except Exception as e:
                _write_failed_response(request_id, task, raw, str(e))
                log.error("generation_parse_failed", request_id=request_id,
                          task=task, raw=raw[:500], error=str(e))
                raise HTTPException(status_code=500, detail={"detail": "Internal error", "request_id": request_id})

    return build_invoke_response(request_id, "generation", task, output, response.usage, model)


# ── Message builders ──────────────────────────────────────────────────────────

def _build_test_cases_message(payload: dict, prompt) -> str:
    """Build the user message for generate_test_cases.
    Conditionally includes snapshot context when available."""
    url = payload["url"]
    page_title = payload.get("page_title") or ""
    snapshot_text = payload.get("snapshot_text")
    interactive_elements = payload.get("interactive_elements")
    locator_source = payload.get("locator_source", "inferred")

    if locator_source == "snapshot" and snapshot_text:
        elements_json = json.dumps(interactive_elements or [], indent=2)
        return (
            f"Analyse this page and generate test cases.\n\n"
            f"URL: {url}\n"
            f"Page title: {page_title}\n\n"
            f"ACCESSIBILITY TREE (from live page — use these exact names and roles):\n"
            f"{snapshot_text}\n\n"
            f"INTERACTIVE ELEMENTS INVENTORY (structured):\n"
            f"{elements_json}\n"
        )
    else:
        return (
            f"Analyse this page and generate test cases.\n"
            f"You have not seen the live page HTML — infer structure from URL and page type.\n\n"
            f"URL: {url}\n"
            f"Page title: {page_title}\n"
        )


def _write_failed_response(request_id: str, task: str, raw: str, error: str) -> None:
    """Write the full raw LLM response to a log file for debugging parse failures."""
    import os
    from datetime import datetime, timezone
    logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, "parse_failures.log")
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"TIMESTAMP : {timestamp}\n")
        f.write(f"REQUEST_ID: {request_id}\n")
        f.write(f"TASK      : {task}\n")
        f.write(f"ERROR     : {error}\n")
        f.write(f"RAW RESPONSE ({len(raw)} chars):\n")
        f.write(raw)
        f.write(f"\n{'='*80}\n")


def _build_script_message(payload: dict, prompt) -> str:
    """Build user message for generate_playwright_script."""
    return (
        f"Generate a Playwright TypeScript test file.\n\n"
        f"Target URL: {payload['url']}\n\n"
        f"Test cases (JSON):\n{json.dumps(payload['test_cases'], indent=2)}\n"
    )
