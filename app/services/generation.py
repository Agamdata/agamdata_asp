"""
ASP-03 Generation Service

Supported tasks:
- draft_email
- summarise_customer
- generate_quote_narrative
- suggest_fields
- draft_whatsapp
- generate_test_cases                    (snapshot/inferred path)
- generate_playwright_script             (TypeScript and Python)
- generate_test_cases_with_inventory     (verified-locator path, no hallucinations)
"""
import json
import re
import structlog
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any

from app.models.request import InvokeRequest
from app.models.response import InvokeResponse
from app.schemas.generation_schemas import (
    GenerateTestCasesPayload,
    GeneratePlaywrightScriptPayload,
    GenerateTestCasesWithInventoryPayload,
)
from app.models.generation_outputs import (
    GenerateTestCasesOutput,
    GenerateTestCasesWithInventoryOutput,
    GeneratePlaywrightScriptOutput,
)
from app.registry import prompt_registry
from app.services._shared import anthropic_client, build_invoke_response, strip_json, strip_script, repair_json
from app.utils.llm_retry import llm_call_with_retry

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
    "generate_test_cases",                    # snapshot/inferred path
    "generate_playwright_script",             # TypeScript and Python
    "generate_test_cases_with_inventory",     # verified-locator path
}

TASK_OUTPUT_SCHEMAS = {
    "draft_email":                            DraftEmailOutput,
    "summarise_customer":                     SummariseCustomerOutput,
    "generate_quote_narrative":               GenerateQuoteNarrativeOutput,
    "suggest_fields":                         SuggestFieldsOutput,
    "draft_whatsapp":                         DraftWhatsappOutput,
    "generate_test_cases":                    GenerateTestCasesOutput,
    "generate_test_cases_with_inventory":     GenerateTestCasesWithInventoryOutput,
    "generate_playwright_script":             GeneratePlaywrightScriptOutput,
}

TASK_PAYLOAD_VALIDATORS = {
    "generate_test_cases":                    GenerateTestCasesPayload,
    "generate_playwright_script":             GeneratePlaywrightScriptPayload,
    "generate_test_cases_with_inventory":     GenerateTestCasesWithInventoryPayload,
}

TASK_MAX_TOKENS = {
    "draft_email":                            1024,
    "summarise_customer":                     1024,
    "generate_quote_narrative":               1024,
    "suggest_fields":                         512,
    "draft_whatsapp":                         512,
    "generate_test_cases":                    32000,
    "generate_test_cases_with_inventory":     12288,  # DEFECT-017: raised from 8192. Truncation confirmed at 8192 for complex inventories.
    "generate_playwright_script":             32000,
}


# ── Main handler ──────────────────────────────────────────────────────────────

async def handle(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    task = req.task
    if task not in VALID_TASKS:
        supported = sorted(VALID_TASKS)
        raise HTTPException(
            status_code=422,
            detail=f"Unknown task '{task}'. Supported: {supported}",
        )

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

    # effective_task tracks the actual execution path.  It matches task in all
    # normal cases but is redirected to "generate_test_cases" when the inventory
    # prompt row is absent (migration 0010 not yet deployed), giving a graceful
    # fallback instead of a 500.
    effective_task = task

    # ── Fetch prompt ──────────────────────────────────────────────────────────
    if task == "generate_test_cases":
        variant = validated_payload.get("locator_source", "inferred")
        prompt = await prompt_registry.get_prompt_variant(
            service_type="generation", task=task,
            caller_module=req.caller_module, maturity_level=maturity,
            ab_variant=variant,
        )

    elif task == "generate_test_cases_with_inventory":
        try:
            prompt = await prompt_registry.get_prompt_variant(
                service_type="generation", task=task,
                caller_module=req.caller_module, maturity_level=maturity,
                ab_variant="inventory",
            )
        except prompt_registry.PromptNotFoundError:
            # Migration 0010 not yet deployed — fall back to snapshot path.
            # No crash, no blocked generation; ops is warned via log.
            log.warning(
                "inventory_prompt_not_deployed_falling_back",
                request_id=request_id,
                task=task,
                detail=(
                    "generate_test_cases_with_inventory prompt row absent from DB. "
                    "Run 'alembic upgrade head' to deploy migration 0010. "
                    "Falling back to generate_test_cases/snapshot path for this request."
                ),
            )
            effective_task = "generate_test_cases"
            prompt = await prompt_registry.get_prompt_variant(
                service_type="generation", task="generate_test_cases",
                caller_module=req.caller_module, maturity_level=maturity,
                ab_variant="snapshot",
            )

    elif task == "generate_playwright_script":
        variant = validated_payload.get("script_variant", "playwright_typescript_pom")
        prompt = await prompt_registry.get_prompt_variant(
            service_type="generation", task=task,
            caller_module=req.caller_module, maturity_level=maturity,
            ab_variant=variant,
        )

    else:
        prompt = await prompt_registry.get_prompt(
            "generation", task, req.caller_module, maturity)

    # ── Build user message ────────────────────────────────────────────────────
    if effective_task == "generate_test_cases" and task == "generate_test_cases_with_inventory":
        # Fallback path: convert the inventory payload into a snapshot-compatible
        # message so the snapshot prompt receives useful element signals.
        user_message = _build_test_cases_message(
            _inventory_payload_to_snapshot(validated_payload), prompt)

    elif effective_task == "generate_test_cases":
        user_message = _build_test_cases_message(validated_payload, prompt)

    elif task == "generate_test_cases_with_inventory":
        # V2 prompt (migration 019) uses template substitution with all fields.
        # V1 prompt (migration 016) uses _build_inventory_message() legacy builder.
        # Detect v2 by checking for {page_type} placeholder in user_prompt_template.
        if "{page_type}" in prompt.user_prompt_template:
            user_message = _build_inventory_message_v2(validated_payload, prompt)
        else:
            user_message = _build_inventory_message(validated_payload, prompt)

    elif task == "generate_playwright_script":
        user_message = _build_script_message(validated_payload, prompt)

    else:
        try:
            user_message = prompt.user_prompt_template.format(**validated_payload)
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required payload field: {e}")

    max_tokens = TASK_MAX_TOKENS.get(effective_task, 2048)
    # DEFECT-016: Use shared retry utility for 529/overload handling
    response = await llm_call_with_retry(
        anthropic_client,
        model=model,
        max_tokens=max_tokens,
        system=prompt.system_prompt,
        messages=[{"role": "user", "content": user_message}],
        request_id=request_id,
    )
    raw = response.content[0].text

    # generate_playwright_script returns raw code — strip fences/labels, wrap directly
    if task == "generate_playwright_script":
        from app.models.generation_outputs import GeneratePlaywrightScriptOutput
        output = GeneratePlaywrightScriptOutput(script=strip_script(raw))
    else:
        # Use effective_task for schema lookup: fallback path uses GenerateTestCasesOutput,
        # not GenerateTestCasesWithInventoryOutput, because the snapshot prompt doesn't
        # emit missing_locators and the caller's GenerationResponse defaults it to [].
        schema_cls = TASK_OUTPUT_SCHEMAS[effective_task]

        # DEFECT-017: Truncation guard — distinguish max_tokens truncation from organic parse error
        stop_reason = getattr(response, 'stop_reason', None)
        if stop_reason == 'max_tokens':
            log.error(
                "generation_truncated",
                request_id=request_id,
                task=task,
                max_tokens=max_tokens,
                raw_length=len(raw),
                stop_reason=stop_reason,
            )
            _write_failed_response(request_id, task, raw, f"Truncated at max_tokens={max_tokens}")
            raise HTTPException(
                status_code=500,
                detail={
                    "detail": f"Generation output exceeded token limit ({max_tokens}). Response truncated.",
                    "request_id": request_id,
                },
            )

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
                          task=task, raw=raw[:500], error=str(e),
                          raw_length=len(raw), max_tokens=max_tokens)
                raise HTTPException(status_code=500, detail={"detail": "Internal error", "request_id": request_id})

    return build_invoke_response(request_id, "generation", task, output, response.usage, model)


# ── Message builders ──────────────────────────────────────────────────────────

def _best_locator(el: dict) -> str:
    """Deterministic Playwright locator selection.

    Priority: testid > id > placeholder > role+name > css fallback.
    getByLabel is intentionally excluded unless name is non-empty AND no
    higher-priority signal exists — unlabelled inputs (name='') must never
    use getByLabel because the label text would be invented by the LLM.
    """
    if el.get("testid"):
        return f"getByTestId('{el['testid']}')"
    if el.get("id"):
        return f"locator('#{el['id']}')"
    if el.get("placeholder"):
        return f"getByPlaceholder('{el['placeholder']}')"
    name = el.get("name", "")
    role = el.get("role", "")
    if name and role:
        return f"getByRole('{role}', {{name: '{name}'}})"
    # Last resort: type or tag CSS selector
    tag = el.get("tag", "")
    el_type = el.get("type", "")
    if el_type:
        return f"locator('{tag}[type=\"{el_type}\"]')"
    return f"locator('{tag}')"


def _format_elements(elements: list) -> str:
    """Format interactive elements with a pre-computed locator on each line.

    The '→ USE:' field gives Claude the exact locator string to copy verbatim.
    This eliminates hallucination: Claude no longer needs to reason about
    locator priority — it just copies the pre-computed value.
    """
    if not elements:
        return "(no structured element data provided)"
    lines = []
    for el in elements:
        attrs = [f"<{el.get('tag', '?')}> role={el.get('role', '')}"]
        if el.get("name"):
            attrs.append(f"name=\"{el['name']}\"")
        if el.get("placeholder"):
            attrs.append(f"placeholder=\"{el['placeholder']}\"")
        if el.get("testid"):
            attrs.append(f"data-testid=\"{el['testid']}\"")
        if el.get("id"):
            attrs.append(f"id=\"{el['id']}\"")
        locator = _best_locator(el)
        lines.append("  " + "  ".join(attrs) + f"  → USE: {locator}")
    return "\n".join(lines)


def _build_test_cases_message(payload: dict, prompt) -> str:
    """Build the user message for generate_test_cases.
    Conditionally includes snapshot context when available."""
    url = payload["url"]
    page_title = payload.get("page_title") or ""
    snapshot_text = payload.get("snapshot_text")
    interactive_elements = payload.get("interactive_elements")
    locator_source = payload.get("locator_source", "inferred")

    if locator_source == "snapshot" and snapshot_text:
        return (
            f"Analyse this page and generate test cases.\n\n"
            f"URL: {url}\n"
            f"Page title: {page_title}\n\n"
            f"ACCESSIBILITY TREE (from live page — use these exact names and roles):\n"
            f"{snapshot_text}\n\n"
            f"INTERACTIVE ELEMENTS INVENTORY (every interactable element on the page):\n"
            f"{_format_elements(interactive_elements or [])}\n"
            f"\nIMPORTANT: Only use locator names, labels, roles, placeholders, and testids "
            f"that appear verbatim in the inventory above. Do NOT invent or paraphrase them.\n"
        )
    else:
        return (
            f"Analyse this page and generate test cases.\n"
            f"You have not seen the live page HTML — infer structure from URL and page type.\n\n"
            f"URL: {url}\n"
            f"Page title: {page_title}\n"
        )


def _inventory_payload_to_snapshot(payload: dict) -> dict:
    """Convert a GenerateTestCasesWithInventoryPayload dict into a dict that
    _build_test_cases_message can consume (snapshot format).

    Used only on the fallback path when migration 0010 is not yet deployed.
    The inventory's recommended locators are embedded as '→ USE:' hints in the
    snapshot_text so the snapshot prompt's pre-computed-locator rule still fires,
    giving the best possible locator quality even without the inventory prompt.
    """
    inventory = payload.get("locator_inventory", [])

    snapshot_lines: list[str] = []
    interactive_elements: list[dict] = []

    for item in inventory:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        locators = item.get("locators", {})
        if hasattr(locators, "model_dump"):
            locators = locators.model_dump()

        name        = item.get("label_text") or item.get("button_text") or item.get("element_name", "")
        tag         = item.get("tag", "input")
        el_type     = item.get("type", "")
        placeholder = item.get("placeholder", "")
        recommended = locators.get("recommended", "")

        # Snapshot text line: mirrors the format expected by the 0008 prompt rule
        role = "button" if tag == "button" else ("link" if tag == "a" else "textbox")
        snapshot_lines.append(
            f"role: {role}  name: \"{name}\""
            + (f"  placeholder: \"{placeholder}\"" if placeholder else "")
            + (f"  → USE: {recommended}" if recommended else "")
        )

        # Interactive element entry for _format_elements()
        interactive_elements.append({
            "tag":        tag,
            "role":       role,
            "name":       name,
            "type":       el_type,
            "placeholder": placeholder,
            "testid":     "",
            "id":         "",
            "forLabel":   "",
        })

    return {
        "url":                  payload.get("url", ""),
        "page_title":           payload.get("page_title") or "",
        "locator_source":       "snapshot",
        "snapshot_text":        "\n".join(snapshot_lines),
        "interactive_elements": interactive_elements,
    }


def _build_inventory_message(payload: dict, prompt) -> str:
    """Build the user message for generate_test_cases_with_inventory.

    Formats each inventory item as a structured text block showing the element
    name, attributes, RECOMMENDED locator, and one fallback.  The LLM is
    instructed by the system prompt to copy RECOMMENDED verbatim — this
    function ensures every relevant signal is visible in the message.
    """
    url = payload["url"]
    page_title = payload.get("page_title") or ""
    inventory = payload.get("locator_inventory", [])

    lines: list[str] = []
    for item in inventory:
        # item may be a dict (raw payload) or a LocatorInventoryItem instance
        if hasattr(item, "model_dump"):
            item = item.model_dump()

        name        = item.get("element_name", "unknown")
        tag         = item.get("tag", "")
        el_type     = item.get("type", "")
        label       = item.get("label_text", "")
        placeholder = item.get("placeholder", "")
        button_text = item.get("button_text", "")
        is_visible  = item.get("is_visible", True)
        locators    = item.get("locators", {})

        # locators may be a dict or a LocatorInventoryLocators instance
        if hasattr(locators, "model_dump"):
            locators = locators.model_dump()

        recommended = locators.get("recommended", "")
        all_verified = locators.get("all_verified", {}) or {}
        is_fragile  = locators.get("is_fragile", False)

        # Header line — element identity
        header = f"  [{name}]  <{tag}"
        if el_type:
            header += f" type={el_type}"
        header += ">"
        if label:
            header += f'  label="{label}"'
        if placeholder:
            header += f'  placeholder="{placeholder}"'
        if button_text:
            header += f'  text="{button_text}"'
        header += f"  visible={str(is_visible).lower()}"
        lines.append(header)

        # Recommended locator (the one the LLM MUST copy verbatim)
        fragile_note = "  \u26a0 FRAGILE \u2014 warn user in playwright_notes" if is_fragile else ""
        lines.append(f"    \u2192 RECOMMENDED: {recommended}{fragile_note}")

        # One fallback (first all_verified entry that differs from recommended)
        fallbacks = [v for v in all_verified.values() if v and v != recommended]
        if fallbacks:
            lines.append(f"    \u2192 FALLBACK:    {fallbacks[0]}")

    inventory_text = "\n".join(lines) if lines else "  (no inventory provided)"

    return (
        f"Generate test cases for this page.\n\n"
        f"URL: {url}\n"
        f"Page title: {page_title}\n\n"
        f"VERIFIED LOCATOR INVENTORY (use RECOMMENDED strings verbatim):\n"
        f"{inventory_text}\n"
    )


def _build_inventory_message_v2(payload: dict, prompt) -> str:
    """Build the user message for generate_test_cases_with_inventory v2 prompt.

    ASP-TSCD-001 CHG-03: Uses prompt template substitution with all F-03-08 and F-03-04
    optional fields. Absent fields render as 'N/A' (same pattern as classify_probe_result).
    """
    import json as _json

    # Format locator inventory as structured text for the prompt
    inventory = payload.get("locator_inventory", [])
    inv_lines = []
    for item in inventory:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        name = item.get("element_name", "unknown")
        tag = item.get("tag", "")
        locators = item.get("locators", {})
        if hasattr(locators, "model_dump"):
            locators = locators.model_dump()
        recommended = locators.get("recommended", "")
        fallback = locators.get("fallback") or locators.get("all_verified", {})
        inv_lines.append(f"  [{name}] <{tag}> → RECOMMENDED: {recommended}")
        if fallback and isinstance(fallback, dict):
            fbs = [v for v in fallback.values() if v and v != recommended]
            if fbs:
                inv_lines.append(f"    FALLBACK: {fbs[0]}")
        elif fallback and isinstance(fallback, str):
            inv_lines.append(f"    FALLBACK: {fallback}")

    inventory_text = "\n".join(inv_lines) if inv_lines else "(no inventory provided)"

    # F-03-08 probe context — optional
    probe_outcome = payload.get("probe_outcome") or "N/A"
    probe_error_messages = str(payload.get("probe_error_messages")) if payload.get("probe_error_messages") else "N/A"
    probe_success_indicators = str(payload.get("probe_success_indicators")) if payload.get("probe_success_indicators") else "N/A"
    submitted_fields = str(payload.get("submitted_fields")) if payload.get("submitted_fields") else "N/A"

    # F-03-04 asset context — optional
    tc_id = payload.get("tc_id") or "N/A"
    test_steps = payload.get("test_steps") or "N/A"
    preconditions_val = payload.get("preconditions") or "N/A"
    expected_result = payload.get("expected_result") or "N/A"
    language = payload.get("language") or "typescript"

    prompt_vars = {
        "url":                      payload.get("url", ""),
        "page_type":                payload.get("page_type", "FORM"),
        "screen_key":               payload.get("screen_key", ""),
        "locator_inventory":        inventory_text,
        "probe_outcome":            probe_outcome,
        "probe_error_messages":     probe_error_messages,
        "probe_success_indicators": probe_success_indicators,
        "submitted_fields":         submitted_fields,
        "tc_id":                    tc_id,
        "test_steps":               test_steps,
        "preconditions":            preconditions_val,
        "expected_result":          expected_result,
        "language":                 language,
    }

    return prompt.user_prompt_template.format(**prompt_vars)


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


def _locator_to_python(js_locator: str) -> str:
    """Convert a JS-style Playwright locator string to its Python API equivalent.

    Examples:
      getByTestId('x')                         -> page.get_by_test_id('x')
      getByPlaceholder('x')                    -> page.get_by_placeholder('x')
      getByRole('button', {name: 'Sign In'})   -> page.get_by_role('button', name='Sign In')
      locator('#id')                           -> page.locator('#id')
    """
    s = js_locator
    s = re.sub(r"\bgetByTestId\(",       "page.get_by_test_id(",       s)
    s = re.sub(r"\bgetByPlaceholder\(",  "page.get_by_placeholder(",   s)
    s = re.sub(r"\bgetByLabel\(",        "page.get_by_label(",         s)
    s = re.sub(r"\bgetByText\(",         "page.get_by_text(",          s)
    # getByRole('role', {name: 'text'})  ->  page.get_by_role('role', name='text')
    s = re.sub(
        r"\bgetByRole\((['\"][\w\s]+['\"]),\s*\{name:\s*(['\"][^'\"]+['\"])\}\)",
        r"page.get_by_role(\1, name=\2)",
        s,
    )
    s = re.sub(r"\blocator\(",            "page.locator(",              s)
    return s


def _extract_locator_map(test_cases: list) -> dict:
    """Deduplicate locators across all test cases into {element_name: primary_locator}.

    Uses the first occurrence of each name so that the map stays stable across
    test cases that reference the same element (e.g. emailField appears in TC_001,
    TC_002, TC_003 — we only need it once).
    """
    result: dict = {}
    for tc in test_cases:
        if not isinstance(tc, dict):
            continue
        for name, loc in (tc.get("locators") or {}).items():
            if name not in result:
                primary = loc.get("primary") if isinstance(loc, dict) else None
                if primary:
                    result[name] = primary
    return result


def _build_script_message(payload: dict, prompt) -> str:
    """Build the user message for generate_playwright_script.

    Uses prompt.user_prompt_template fetched from the DB — not a hardcoded
    string. Template keys: {url}, {test_cases_json}.
    Migration 0013 seeds PYTHON_USER and TS_USER templates that use these keys.
    """
    template_vars = {
        'url':             payload.get('url', ''),
        'test_cases_json': json.dumps(payload.get('test_cases', []), indent=2),
    }
    return prompt.user_prompt_template.format(**template_vars)
