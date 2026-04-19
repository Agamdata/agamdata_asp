# app/models/generation_schemas.py
# v2.1 — LLM output coercion fixes for generate_test_cases_with_inventory
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, Literal, Any


# ── Locator ───────────────────────────────────────────────────────────────────

class LocatorOutput(BaseModel):
    """Locator for one element in a test case.
    primary and fallback MUST be verbatim strings from the inventory.
    extra='ignore' — future inventory fields never break parsing.
    """
    model_config = ConfigDict(extra='ignore')

    primary:      str
    fallback:     Optional[str] = None
    strategy:     str
    locator_type: Optional[str] = None
    # FIXED (Issue 4): was missing — now declared and preserved
    # Values: label | role | testid | text | placeholder | css

    confidence:   Optional[str] = None
    # FIXED (Issue 4): was missing — now declared and preserved
    # Values: high | medium | low


# ── Step ──────────────────────────────────────────────────────────────────────

class StepOutput(BaseModel):
    """One step in a test case.

    target semantics (FIXED — Issue 2):
      action=navigate                              → target is the full URL
      action=fill|click|press|select|assert_visible|assert_text
                                                   → target is element_name from inventory
      action=assert_url                            → target is expected URL or path fragment
      action=screenshot                            → target is optional filename

    locator semantics (FIXED — Issue 2):
      interactive steps (fill/click/press/select/assert_visible/assert_text)
                        → locator is the recommended string from inventory, verbatim
      navigate | assert_url | screenshot           → locator is null
    """
    model_config = ConfigDict(extra='ignore')

    step_number: int
    action:      str
    # Allowed: fill | click | navigate | assert | select | hover
    locator:     Optional[str] = None
    # Must match a locator from locator_inventory input (null for navigate/assert steps)
    value:       Optional[str] = None
    # Required for fill/select, null otherwise
    description: Optional[str] = None
    # Human-readable step description
    # REMOVED in v3 (migration 020): target — redundant with locator (PAP Q-2)


# ── Test Case ─────────────────────────────────────────────────────────────────

class TestCaseOutput(BaseModel):
    """v3 schema (migration 020) — simplified per PAP field consumption audit.

    REMOVED in v3: id (not stored), seed_data (never consumed, DEFECT-013),
    playwright_notes (broken DEFECT-015, never consumed), locators dict (redundant).
    extra='ignore' during migration window — old-format LLM responses with removed
    fields won't 422. Change to 'forbid' after 1 sprint stability confirmation.
    """
    model_config = ConfigDict(extra='ignore')

    name:            str
    priority:        Literal['Critical', 'High', 'Medium', 'Low']
    category:        str = "Functional"
    description:     str
    preconditions:   list[str]
    steps:           list[StepOutput]
    expected_result: str

    @field_validator('priority', mode='before')
    @classmethod
    def normalise_priority(cls, v):
        """Normalise 'critical'/'HIGH'/'medium' → 'Critical'/'High'/'Medium'.

        The inventory prompt does not enforce casing on priority values so
        the LLM returns all-lowercase. The Literal check requires title-case.
        capitalize() handles lower, upper, and mixed inputs correctly.
        """
        if isinstance(v, str):
            return v.capitalize()
        return v

    @field_validator('preconditions', mode='before')
    @classmethod
    def normalise_preconditions(cls, v):
        """Coerce a bare string to a single-item list.

        The old generate_test_cases prompt returns preconditions as a plain
        string. This validator keeps the old task working after the type change
        while the new inventory task returns a proper list.
        """
        if isinstance(v, str):
            return [v]
        return v

    # REMOVED: coerce_playwright_notes — field removed in v3 (migration 020)
    # REMOVED: coerce_seed_data — field removed in v3 (migration 020)


# ── Page Analysis ─────────────────────────────────────────────────────────────

class PageAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra='ignore')

    page_type:     str
    complexity:    Literal['low', 'medium', 'high']
    # FIXED (Issue 5): validator normalises 'Medium'/'HIGH' to lowercase before Literal check
    summary:       str
    primary_flows: list[str] = []
    # detected_elements and tech_stack_hints removed — PAP-TSCD-005 v1.1 CORR-03.
    # They are not in the OUTPUT CONTRACT and are not used downstream.
    # extra='ignore' means any LLM that still emits them will not fail.

    @model_validator(mode='before')
    @classmethod
    def remap_llm_field_aliases(cls, data: Any) -> Any:
        """Map alternative field names the LLM may return to their canonical names.

        The inventory prompt does not pin field names tightly, so the LLM
        uses different keys across calls. We try every observed alias in
        priority order and synthesise a fallback if none match, so parsing
        never fails regardless of which variant the LLM produces.

        summary aliases (tried in order):
          primary_function, description, page_description, primary_purpose
        primary_flows aliases:
          key_user_flows, primary_actions, user_flows, key_flows
        complexity:
          defaults to 'medium' when absent
        """
        if not isinstance(data, dict):
            return data

        # ── summary ──────────────────────────────────────────────────────────
        if 'summary' not in data:
            _summary_aliases = (
                'primary_function', 'description',
                'page_description', 'primary_purpose',
            )
            for alias in _summary_aliases:
                if alias in data:
                    data['summary'] = data[alias]
                    break
            else:
                # No alias found — synthesise from page_type + primary_actions
                page_type = data.get('page_type', 'page')
                flows = (
                    data.get('primary_actions')
                    or data.get('key_user_flows')
                    or data.get('key_flows')
                    or []
                )
                readable = page_type.replace('_', ' ').title()
                if flows:
                    sample = ', '.join(str(f) for f in flows[:3])
                    data['summary'] = f"{readable} — key actions: {sample}"
                else:
                    data['summary'] = readable

        # ── primary_flows ─────────────────────────────────────────────────────
        if 'primary_flows' not in data:
            for alias in (
                'key_user_flows', 'primary_actions', 'user_flows',
                'key_flows', 'key_elements', 'primary_elements',
            ):
                if alias in data:
                    data['primary_flows'] = data[alias]
                    break

        # ── complexity ────────────────────────────────────────────────────────
        if 'complexity' not in data:
            data['complexity'] = 'medium'

        return data

    @field_validator('complexity', mode='before')
    @classmethod
    def normalise_complexity(cls, v):
        """Normalise 'Medium' / 'HIGH' / 'Low' → 'medium' / 'high' / 'low'."""
        if isinstance(v, str):
            return v.lower()
        return v


# ── Top-level: generate_test_cases (old task — kept for backwards compatibility)

class GenerateTestCasesOutput(BaseModel):
    """
    Claude MUST return JSON matching this schema exactly.
    No markdown. No backticks. No prose outside the JSON object.
    """
    model_config = ConfigDict(extra='ignore')

    page_analysis: PageAnalysisOutput
    test_cases:    list[TestCaseOutput] = Field(min_length=1, max_length=20)


# ── Top-level: generate_test_cases_with_inventory (new task) ─────────────────

class GenerateTestCasesWithInventoryOutput(BaseModel):
    """Output schema for the verified-locator inventory path.

    missing_locators is REQUIRED — empty list [] when every test step
    has a matching inventory element; populated when the LLM needed an
    element that was not in the inventory.

    covered_categories (v2.0 addition, ASP-OUT-013 / S-1): the LLM
    reports which test-case categories it actually generated. Always
    present; subset of payload.categories_to_generate when that was
    provided; self-selected coverage when payload.categories_to_generate
    was None. Empty list is semantically valid but flags a generation-
    quality concern; callers SHOULD warn on empty covered_categories
    when test_cases is non-empty.
    """
    model_config = ConfigDict(extra='ignore')

    # v3 (migration 020): page_analysis removed — not in redesigned schema
    test_cases:         list[TestCaseOutput] = Field(min_length=1, max_length=20)
    missing_locators:   list[str] = []
    covered_categories: list[str] = []          # v2.0 addition (S-1)


# ── Top-level: generate_playwright_script ────────────────────────────────────

class GeneratePlaywrightScriptOutput(BaseModel):
    """
    Claude MUST return a JSON object with a single 'script' field
    containing the complete TypeScript file as a string.
    """
    script: str        # complete TypeScript or Python file content
