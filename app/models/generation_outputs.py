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
    # Allowed: navigate | fill | click | press | select |
    #          assert_url | assert_visible | assert_text | screenshot
    target:      Optional[str] = None
    locator:     Optional[str] = None
    # FIXED (Issue 2): was missing entirely — must match recommended string verbatim
    value:       Optional[str] = None
    description: Optional[str] = None
    # FIXED (Issue 2): was required str — now Optional so old and new responses both validate


# ── Test Case ─────────────────────────────────────────────────────────────────

class TestCaseOutput(BaseModel):
    model_config = ConfigDict(extra='ignore')

    id:          str
    name:        str
    priority:    Literal['Critical', 'High', 'Medium', 'Low']
    category:    str = "Functional"
    # Allowed: Authentication | Form | Navigation | E2E | Accessibility
    #        | Grid | Validation | API | Functional | Performance | Negative
    # (Canonical 11-value list — PAP-TSCD-005 v1.1 CORR-04)
    # Default: "Functional" — used when the LLM omits the field (pre-migration-0015).
    # Once OUTPUT CONTRACT (0015) is deployed the LLM will always supply it.
    description: str
    preconditions: list[str]
    # FIXED (Issue 3): was str — now list[str].
    # Validator below coerces bare strings so old-task responses still parse.

    steps:            list[StepOutput]
    locators:         dict[str, LocatorOutput] = Field(default_factory=dict)
    # FIXED: LLM omits locators on pre-0015 prompts. OUTPUT CONTRACT mandates
    # the key is present (may be {}). Default to {} so parsing never fails.
    # Same pattern as seed_data below.
    seed_data:        dict | None = Field(default_factory=dict)
    # FIXED: was required dict — LLM omits this field or returns null when no
    # seed data is needed (e.g. read-only pages). Default to {} so parsing never fails.
    # Accepts None (LLM returns null) — coerced to {} by validator below.
    expected_result:  str
    playwright_notes: Optional[str] = None

    @field_validator('seed_data', mode='before')
    @classmethod
    def coerce_seed_data(cls, v):
        """Coerce null → {} so LLM returning seed_data:null doesn't fail parsing."""
        if v is None:
            return {}
        return v

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

    @field_validator('playwright_notes', mode='before')
    @classmethod
    def coerce_playwright_notes(cls, v):
        """Coerce [] → None and [str, ...] → newline-joined string.

        The inventory prompt returns playwright_notes as a JSON array.
        The schema declares it Optional[str]. Accept both forms so the
        response always parses regardless of how the LLM serialises it.
        """
        if isinstance(v, list):
            return '\n'.join(str(item) for item in v) if v else None
        return v


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
    """
    model_config = ConfigDict(extra='ignore')

    page_analysis:    PageAnalysisOutput
    test_cases:       list[TestCaseOutput] = Field(min_length=1, max_length=20)
    missing_locators: list[str] = []


# ── Top-level: generate_playwright_script ────────────────────────────────────

class GeneratePlaywrightScriptOutput(BaseModel):
    """
    Claude MUST return a JSON object with a single 'script' field
    containing the complete TypeScript file as a string.
    """
    script: str        # complete TypeScript or Python file content
