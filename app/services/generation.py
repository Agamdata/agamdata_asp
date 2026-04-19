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
import asyncio
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
    RefactorScriptLocatorsPayload,
    RefactorScriptLocatorsResult,
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
    "refactor_script_locators",               # v2.0 — I-024-07
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
    "refactor_script_locators":               RefactorScriptLocatorsResult,   # v2.0 — I-024-07
}

TASK_PAYLOAD_VALIDATORS = {
    "generate_test_cases":                    GenerateTestCasesPayload,
    "generate_playwright_script":             GeneratePlaywrightScriptPayload,
    "generate_test_cases_with_inventory":     GenerateTestCasesWithInventoryPayload,
    "refactor_script_locators":               RefactorScriptLocatorsPayload,  # v2.0 — I-024-07
}

TASK_MAX_TOKENS = {
    "draft_email":                            1024,
    "summarise_customer":                     1024,
    "generate_quote_narrative":               1024,
    "suggest_fields":                         512,
    "draft_whatsapp":                         512,
    "generate_test_cases":                    32000,
    "generate_test_cases_with_inventory":     12288,  # DEFECT-017: raised from 8192
    "generate_playwright_script":             32000,
    "refactor_script_locators":               8192,   # v2.0 §9.6 — I-024-07
}

# v2.0 (§11 I-024-03 / OQ-2 ruling): interactive-panel ceiling.
# Applied when caller_module == "test_generator" AND task ==
# "generate_test_cases_with_inventory". 28s inner wrapper leaves 2s for
# parsing + response assembly within the 30s caller SLA.
TEST_GENERATOR_INTERACTIVE_TIMEOUT_SECONDS = 28.0


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

    elif task == "refactor_script_locators":
        # v2.0 — I-024-06. Build the refactor prompt from aligned payload
        # placeholders (script_body, locator_diff, screen_key, language).
        # locator_diff is a list[LocatorDiffItem]; render as JSON so the
        # LLM sees structured old→new pairs.
        locator_diff_rendered = json.dumps(
            validated_payload.get("locator_diff", []), indent=2, default=str
        )
        user_message = prompt.user_prompt_template.format(
            script_body=validated_payload.get("script_body", ""),
            locator_diff=locator_diff_rendered,
            screen_key=validated_payload.get("screen_key", ""),
            language=validated_payload.get("language", "typescript"),
        )

    else:
        try:
            user_message = prompt.user_prompt_template.format(**validated_payload)
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required payload field: {e}")

    max_tokens = TASK_MAX_TOKENS.get(effective_task, 2048)
    # F-03-04 uses same max_tokens as F-03-08 — LLM generates freely,
    # handler truncates to 1 TC post-parse. max_tokens cap doesn't help
    # because truncated JSON is unparseable.
    # DEFECT-016: Use shared retry utility for 529/overload handling.
    #
    # v2.0 I-024-05 / OQ-2 ruling: F-01-10 interactive ceiling (30s caller
    # SLA). Wrap the LLM call in asyncio.wait_for(28s) for
    # caller_module="test_generator" on generate_test_cases_with_inventory.
    # On timeout: 504 Gateway Timeout. max_tokens (lowered for interactive
    # via prompt instruction, RULE 9) is the primary self-bounding
    # mechanism; wait_for is the secondary guard.
    llm_call = llm_call_with_retry(
        anthropic_client,
        model=model,
        max_tokens=max_tokens,
        system=prompt.system_prompt,
        messages=[{"role": "user", "content": user_message}],
        request_id=request_id,
    )
    if (req.caller_module == "test_generator"
            and task == "generate_test_cases_with_inventory"):
        try:
            response = await asyncio.wait_for(
                llm_call,
                timeout=TEST_GENERATOR_INTERACTIVE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            log.warning(
                "generation_interactive_timeout",
                request_id=request_id,
                caller_module=req.caller_module,
                caller_feature=req.caller_feature,
                timeout_s=TEST_GENERATOR_INTERACTIVE_TIMEOUT_SECONDS,
            )
            raise HTTPException(
                status_code=504,
                detail=(
                    "Interactive generation timeout "
                    f"({int(TEST_GENERATOR_INTERACTIVE_TIMEOUT_SECONDS)}s). "
                    "Retry with a narrower categories_to_generate or lower inventory size."
                ),
            )
    else:
        response = await llm_call

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
        # DEFECT-017: Truncation guard — max_tokens=12288 for all modes now.
        # F-03-04 count enforcement is handler post-processing, not max_tokens cap.
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

    # Post-processing: enforce test case count for with_inventory task
    if task == "generate_test_cases_with_inventory":
        output = _enforce_test_case_count(output, validated_payload, request_id)

    return build_invoke_response(request_id, "generation", task, output, response.usage, model)


# ── Count enforcement ─────────────────────────────────────────────────────────

def _enforce_test_case_count(result, payload: dict, request_id: str):
    """Enforce test case count per caller mode. Post-processing — LLM count
    instructions are unreliable.

    F-03-04 (tc_id or test_steps present): exactly 1 test case.
    F-03-08 (probe context): up to 5, no truncation needed.
    """
    from app.models.generation_outputs import GenerateTestCasesWithInventoryOutput

    is_f03_04 = bool(payload.get("tc_id") or payload.get("test_steps"))

    if is_f03_04 and len(result.test_cases) > 1:
        log.info(
            "test_case_count_truncated",
            request_id=request_id,
            original_count=len(result.test_cases),
            enforced_count=1,
            mode="F-03-04",
            reason="F-03-04 requires exactly one test case; LLM generated more",
        )
        return GenerateTestCasesWithInventoryOutput(
            test_cases=[result.test_cases[0]],
            missing_locators=result.missing_locators,
        )

    return result


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


def _build_generation_instructions(payload: dict) -> str:
    """Determine call mode from payload context and return explicit count instruction.

    v2.0 (I-024-03, I-024-04):
      - If payload.categories_to_generate is non-empty, it overrides mode-based
        category selection — generate EXACTLY len(list) test cases over those
        categories only (S-1).
      - Appends a live-extracted locator-source advisory when
        payload.locator_source == "live_extracted" (S-3).

    Legacy modes (preserved):
      F-03-04 mode: test_steps or tc_id present → 1 test case.
      F-03-08 mode: probe context or default → 5 test cases.
    """
    categories = payload.get("categories_to_generate") or []
    locator_source = payload.get("locator_source") or "verified"

    # v2.0 S-1 override: coverage-aware generation
    if categories:
        base = (
            f"MODE: Coverage-aware generation (v2.0).\n"
            f"Generate EXACTLY {len(categories)} test cases covering ONLY "
            f"these categories: {categories}.\n"
            "Populate covered_categories in the response with exactly this list "
            "(or a subset if any category could not be addressed given the inventory).\n"
            "Do not generate test cases for any other category."
        )
    else:
        is_f03_04 = bool(payload.get("tc_id") or payload.get("test_steps"))
        if is_f03_04:
            base = (
                "MODE: Engineer-triggered script generation (F-03-04).\n"
                "Generate EXACTLY ONE test case covering the primary happy path.\n"
                "Do not generate edge cases, negative tests, or validation scenarios.\n"
                "The engineer will add those manually if needed.\n"
                f"Test case ID for reference: {payload.get('tc_id') or 'N/A'}"
            )
        else:
            probe_context_note = ""
            if payload.get("probe_error_messages"):
                probe_context_note = (
                    f"\nProbe observed these errors — use them to sharpen TC-2 and TC-3: "
                    f"{payload.get('probe_error_messages')}"
                )
            base = (
                "MODE: Automated probe-context generation (F-03-08).\n"
                "Generate EXACTLY FIVE test cases in this order:\n"
                "TC-1: Happy path — correct data, all required fields, successful submission.\n"
                "TC-2: Required field validation — omit required fields, verify error response.\n"
                "TC-3: Invalid data format — malformed inputs (bad email, invalid phone format).\n"
                "TC-4: Boundary values — empty strings, maximum length, special characters.\n"
                "TC-5: Unauthorised access — session expiry or missing auth, verify redirect.\n"
                "Do not generate fewer than five test cases. Do not generate more than five."
                + probe_context_note
            )

    # v2.0 S-3 (I-024-04): live_extracted advisory
    if locator_source == "live_extracted":
        base += (
            "\n\nNote: locators are live-extracted and best-effort. Flag fragile "
            "locators in missing_locators with a short reason."
        )

    return base


def _build_form_data_context(payload: dict) -> str:
    """Render the FORM_DATA_BLOCK content for the v4 user-prompt template (S-2).

    When payload.form_data is populated, render the caller-supplied seed values
    so the LLM uses them as realistic test data in step value fields.
    When absent, instruct the LLM to synthesise realistic values.
    """
    form_data = payload.get("form_data")
    if form_data:
        return (
            "Use these field values as realistic test data in step value fields: "
            f"{form_data}"
        )
    return (
        "No form data provided — generate realistic test values from field "
        "names and page context."
    )


def _build_probe_context(payload: dict) -> str:
    """Render probe context section. N/A when fields absent (F-03-04 mode)."""
    if not any([payload.get("probe_outcome"), payload.get("probe_error_messages"),
                payload.get("probe_success_indicators"), payload.get("submitted_fields")]):
        return "No probe context — engineer-triggered generation."

    return (
        f"Probe outcome: {payload.get('probe_outcome') or 'N/A'}\n"
        f"Error messages observed: {payload.get('probe_error_messages') or 'N/A'}\n"
        f"Success indicators observed: {payload.get('probe_success_indicators') or 'N/A'}\n"
        f"Fields submitted during probe: {payload.get('submitted_fields') or 'N/A'}"
    )


def _format_inventory_text(payload: dict) -> str:
    """Format locator inventory as structured text for prompt substitution."""
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
        inv_lines.append(f"  [{name}] <{tag}> \u2192 RECOMMENDED: {recommended}")
        if fallback and isinstance(fallback, dict):
            fbs = [v for v in fallback.values() if v and v != recommended]
            if fbs:
                inv_lines.append(f"    FALLBACK: {fbs[0]}")
        elif fallback and isinstance(fallback, str):
            inv_lines.append(f"    FALLBACK: {fallback}")
    return "\n".join(inv_lines) if inv_lines else "(no inventory provided)"


def _build_inventory_message_v2(payload: dict, prompt) -> str:
    """Build the user message for generate_test_cases_with_inventory v2/v3 prompt.

    v3 (migration 020): Uses {generation_instructions} + {probe_context} template vars.
    v2 (migration 019): Uses individual field substitution (legacy).
    Detection: v3 template contains {generation_instructions}.
    """
    inventory_text = _format_inventory_text(payload)

    # v3/v4 prompt — uses generation_instructions + probe_context.
    # v4 (migration 024) additionally uses form_data_context (I-024-03 / S-2).
    if "{generation_instructions}" in prompt.user_prompt_template:
        prompt_vars = {
            "url":                      payload.get("url", ""),
            "page_type":                payload.get("page_type", "FORM"),
            "screen_key":               payload.get("screen_key", ""),
            "locator_inventory":        inventory_text,
            "generation_instructions":  _build_generation_instructions(payload),
            "probe_context":            _build_probe_context(payload),
            # v4 (migration 024) — present in v4 templates, harmless extra key
            # for v3 templates because str.format ignores unreferenced kwargs.
            "form_data_context":        _build_form_data_context(payload),
        }
        return prompt.user_prompt_template.format(**prompt_vars)

    # v2 prompt (migration 019) — individual field substitution
    probe_outcome = payload.get("probe_outcome") or "N/A"
    probe_error_messages = str(payload.get("probe_error_messages")) if payload.get("probe_error_messages") else "N/A"
    probe_success_indicators = str(payload.get("probe_success_indicators")) if payload.get("probe_success_indicators") else "N/A"
    submitted_fields = str(payload.get("submitted_fields")) if payload.get("submitted_fields") else "N/A"
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
