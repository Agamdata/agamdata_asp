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
    """Verified locator set for one inventory element."""
    model_config = ConfigDict(extra="ignore")  # ADR-033
    recommended: str                    # verbatim Playwright call — LLM must copy this
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

    locator_source: Always 'verified' — by-design per-task restriction.
    The whole point of with_inventory is that locators are verified.
    """
    model_config = ConfigDict(extra="ignore")  # ADR-033
    url: str
    page_title: Optional[str] = None
    locator_source: Literal["verified"] = "verified"
    locator_inventory: List[LocatorInventoryItem] = Field(min_length=1)


class GeneratePlaywrightScriptPayload(BaseModel):
    """Validated payload for generate_playwright_script task."""
    model_config = ConfigDict(extra="ignore")  # ADR-033
    url: str
    test_cases: List[dict]
    script_variant: str = "playwright_typescript_pom"
    title_format: Optional[str] = None
    title_format_example: Optional[str] = None
