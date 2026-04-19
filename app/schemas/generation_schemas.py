"""
ASP-03 Generation Service — Pydantic Payload Schemas (ADR-024, ADR-033)

Request payload models for generation tasks.
Generation payloads use ConfigDict(extra='ignore') per ADR-033:
- PAP sends caller context fields that evolve with test scenarios
- Unknown fields are silently dropped with INFO log for observability
- This is a documented exception to ADR-008 (which mandates extra='forbid')
- NLP and all other services retain extra='forbid'

File: app/schemas/generation_schemas.py
Spec: ASP-FEAT-ASP-03 v1.1, Section 7
"""
import structlog
from typing import Literal, Optional, List

from pydantic import BaseModel, ConfigDict, Field

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------

class InteractiveElement(BaseModel):
    """Single interactive element extracted from page DOM."""
    model_config = ConfigDict(extra="ignore")  # ADR-033
    tag: str
    role: str
    name: str = ""
    type: str = ""
    placeholder: str = ""
    testid: str = ""
    id: str = ""
    forLabel: str = ""


class LocatorInventoryLocators(BaseModel):
    """Verified locator set for one inventory element.

    CHG-02: formally governed fields are recommended (required) and fallback (optional).
    all_verified and is_fragile are retained for backward compatibility with
    _build_inventory_message() handler.
    """
    model_config = ConfigDict(extra="ignore")  # ADR-033
    recommended: str                    # Required. verbatim Playwright call — LLM must copy
    fallback: Optional[str] = None      # CHG-02: Optional second-best strategy
    all_verified: dict[str, str] = {}   # every strategy that resolved to exactly 1 element
    is_fragile: bool = False            # true when recommended is css_fallback only


class LocatorInventoryItem(BaseModel):
    """One element entry in the verified locator inventory.

    Phase 2 synthetic call (4 elements: first_name/email/phone/submit)
    used this exact shape and produced 5 valid test cases — this is the contract.
    """
    model_config = ConfigDict(extra="ignore")  # ADR-033
    element_name: str                   # snake_case identifier, e.g. email_input
    tag: str                            # HTML tag: input | button | a | select | textarea
    type: str = ""                      # input type attr; empty for buttons/links
    label_text: str = ""               # text from <label> or aria-label; empty if none
    placeholder: str = ""              # placeholder attr value; empty if none
    button_text: str = ""              # visible text of button/link (trimmed to 80 chars)
    is_visible: bool = True            # element has non-zero bounding box on page
    locators: LocatorInventoryLocators


# ---------------------------------------------------------------------------
# Task-specific payload models (Section 7.1, 7.2)
# ---------------------------------------------------------------------------

class GenerateTestCasesPayload(BaseModel):
    """Validated payload for generate_test_cases task.

    locator_source: 'snapshot' (live page data) or 'inferred' (URL-only).
    D-1: Restricted to these two values. 'verified' belongs to with_inventory task.
    """
    model_config = ConfigDict(extra="ignore")  # ADR-033
    url: str
    snapshot_text: Optional[str] = None
    interactive_elements: Optional[List[InteractiveElement]] = None
    page_title: Optional[str] = None
    locator_source: Literal["snapshot", "inferred"] = "inferred"


class GenerateTestCasesWithInventoryPayload(BaseModel):
    """Validated payload for generate_test_cases_with_inventory task.

    v2.0 additions (ASP-FEAT-ASP-03 v2.0, ASP-OUT-013):
      - locator_source widened to include "live_extracted" (S-3)
      - categories_to_generate (S-1)
      - covered_categories (S-1, consumer-echo symmetry; not currently
        rendered by v4 prompts but available for future multi-call
        de-duplication scenarios)
      - form_data (S-2)

    Three calling modes after v2.0:
      F-03-08 (probe context): probe_outcome, probe_error_messages, etc.
      F-03-04 (asset context): test_steps, preconditions, tc_id, language, etc.
      F-01-10 (interactive live panel): caller_module="test_generator",
               typically locator_source="live_extracted", form_data populated.
    All mode-specific fields are optional — handler renders absent fields as 'N/A'.
    """
    model_config = ConfigDict(extra="ignore")  # ADR-033

    # --- Always required (all features) ---
    url: str
    page_type: str = "FORM"                     # CHG-06: sent by PAP as 'FORM'
    screen_key: str = ""                         # CHG-06: sent by PAP always
    locator_source: Literal["verified", "live_extracted"] = "verified"   # v2.0: widened (S-3)
    locator_inventory: List[LocatorInventoryItem] = Field(min_length=1)

    # --- Optional metadata (retained) ---
    page_title: Optional[str] = None

    # --- F-03-08 only (probe context) ---
    probe_outcome: Optional[str] = None
    probe_error_messages: Optional[List[str]] = None
    probe_success_indicators: Optional[List[str]] = None
    submitted_fields: Optional[dict] = None

    # --- F-03-04 only (asset context) ---
    test_steps: Optional[str] = None
    preconditions: Optional[str] = None
    expected_result: Optional[str] = None
    tc_id: Optional[str] = None
    language: Optional[Literal["typescript", "python"]] = None

    # --- v2.0 additions (ASP-OUT-013) ---
    categories_to_generate: Optional[List[str]] = None   # S-1: caller selects subset
    covered_categories: Optional[List[str]] = None        # S-1: consumer-echo symmetry (not rendered in v4 prompt)
    form_data: Optional[dict[str, str]] = None           # S-2: seed values for realistic test data


# ---------------------------------------------------------------------------
# refactor_script_locators models (v2.0 new task, §S-5)
# ---------------------------------------------------------------------------

class LocatorDiffItem(BaseModel):
    """One entry in a locator_diff list — a single old→new replacement."""
    model_config = ConfigDict(extra="forbid")
    element_name: str
    old_locator: str
    new_locator: str
    change_type: Optional[str] = None          # optional hint: "role" | "attr" | "text" | other


class RefactorScriptLocatorsPayload(BaseModel):
    """Validated payload for refactor_script_locators task.

    Aligned to ASP-OUT-012 authoritative prompt-template placeholders.
    `locator_diff` is a list of replacements to apply (NOT a full inventory).
    """
    model_config = ConfigDict(extra="ignore")  # ADR-033
    script_body: str
    locator_diff: List[LocatorDiffItem]
    screen_key: str
    language: str = "typescript"


class RefactorScriptLocatorsResult(BaseModel):
    """Output model for refactor_script_locators task.

    Aligned to ASP-OUT-012 output JSON schema:
      refactored_script, changes_made, unchanged_locators, warnings.
    """
    model_config = ConfigDict(extra="ignore")
    refactored_script: str
    changes_made: List[str] = []
    unchanged_locators: List[str] = []
    warnings: List[str] = []


class GeneratePlaywrightScriptPayload(BaseModel):
    """Validated payload for generate_playwright_script task."""
    model_config = ConfigDict(extra="ignore")  # ADR-033
    url: str
    test_cases: List[dict]
    script_variant: str = "playwright_typescript_pom"
    title_format: Optional[str] = None
    title_format_example: Optional[str] = None
