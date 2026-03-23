# app/models/generation_schemas.py
# Pydantic output schemas for ASP-03 generation tasks
from pydantic import BaseModel, Field
from typing import Optional, Literal


# ── Locator ───────────────────────────────────────────────────────────────────

class LocatorOutput(BaseModel):
    primary: str
    fallback: Optional[str] = None
    strategy: str


# ── Step ──────────────────────────────────────────────────────────────────────

class StepOutput(BaseModel):
    step_number: int
    action: str
    # action values: navigate | fill | click | press | select |
    #                expect_visible | expect_text | expect_url | screenshot
    target: Optional[str] = None   # locator string or URL
    value: Optional[str] = None    # fill value, key name, expected text
    description: str


# ── Test Case ─────────────────────────────────────────────────────────────────

class TestCaseOutput(BaseModel):
    id: str                        # TC-001, TC-002 ...
    name: str
    priority: Literal["Critical", "High", "Medium", "Low"]
    category: str
    # Allowed: Authentication | Navigation | Form | Functional |
    #           E2E | Accessibility | Performance | Negative
    description: str
    preconditions: str
    steps: list[StepOutput]
    locators: dict[str, LocatorOutput]
    seed_data: dict
    expected_result: str
    playwright_notes: Optional[str] = None


# ── Page Analysis ─────────────────────────────────────────────────────────────

class PageAnalysisOutput(BaseModel):
    page_type: str
    complexity: Literal["low", "medium", "high"]
    summary: str
    primary_flows: list[str] = []
    detected_elements: list[str] = []
    tech_stack_hints: list[str] = []


# ── Top-level: generate_test_cases ───────────────────────────────────────────

class GenerateTestCasesOutput(BaseModel):
    """
    Claude MUST return JSON matching this schema exactly.
    No markdown. No backticks. No prose outside the JSON object.
    """
    page_analysis: PageAnalysisOutput
    test_cases: list[TestCaseOutput] = Field(min_length=1, max_length=15)


# ── Top-level: generate_playwright_script ────────────────────────────────────

class GeneratePlaywrightScriptOutput(BaseModel):
    """
    Claude MUST return a JSON object with a single 'script' field
    containing the complete TypeScript file as a string.
    """
    script: str        # complete TypeScript file content
