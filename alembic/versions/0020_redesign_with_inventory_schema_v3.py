"""Redesign generate_test_cases_with_inventory prompt — simplified schema v3

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-16

Resolves: OPS-003 (truncation), DEFECT-015 (playwright_notes), DEFECT-017 (permanent fix)
Trigger: PAP field consumption audit + requirements clarification (Q-1 through Q-4)

Changes from v2 (migration 019):
- Test case count: 1 for F-03-04, 5 for F-03-08 (was: unconstrained)
- Removed from output: seed_data, playwright_notes, locators dict, id, target
- Simplified StepOutput: step_number, action, locator, value, description
- Mode detection via {generation_instructions} + {probe_context} template vars
- Output volume reduction: ~86-96% vs v2

Atrium-transition relevance: REPLICATE
"""
from alembic import op
from sqlalchemy import text

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

SYSTEM_PROMPT_V3 = """\
You are a Playwright test case generator for automated testing pipelines.
You receive verified page element locators and contextual information about a form page.
Generate structured test cases using ONLY the locators provided in the input.

STRICT RULES:
1. Use ONLY locators from locator_inventory. Never suggest, infer, or create locators
   for elements not in the inventory.
2. For every element referenced in test steps that does not appear in the inventory,
   add a plain-English description to missing_locators.
   Example: "phone_field: referenced in test flow but no verified locator in inventory"
3. Generate the number of test cases specified in the generation instructions below.
   Do not exceed the specified count.
4. Every step locator string must exactly match a locator value from the input
   locator_inventory. Do not paraphrase or abbreviate locator strings.
5. Return ONLY valid JSON matching the schema below.
   No markdown fences. No preamble. No explanation outside the JSON.

Output JSON schema \u2014 follow exactly:
{
  "test_cases": [
    {
      "name": "string \u2014 descriptive test case name",
      "priority": "Critical|High|Medium|Low",
      "category": "string \u2014 e.g. Form|Navigation|Validation|Authentication",
      "description": "string \u2014 what this test case verifies",
      "preconditions": ["string \u2014 prerequisite condition"],
      "steps": [
        {
          "step_number": 1,
          "action": "fill|click|navigate|assert|select|hover",
          "locator": "string \u2014 exact locator from inventory",
          "value": "string or null",
          "description": "string \u2014 plain English step description"
        }
      ],
      "expected_result": "string \u2014 what a passing test looks like"
    }
  ],
  "missing_locators": ["string \u2014 element name: reason not found in inventory"]
}"""

USER_PROMPT_V3 = """\
Page URL: {url}
Page type: {page_type}
Screen key: {screen_key}

Verified locator inventory \u2014 use ONLY these locators in step locator fields:
{locator_inventory}

--- Generation Instructions ---
{generation_instructions}

--- Behavioral Probe Context ---
{probe_context}

Generate test cases now."""


# V2 content for downgrade — copied from migration 019 DB row (I-020-01 verified)
SYSTEM_PROMPT_V2 = """\
You are a Playwright test case generator for automated testing pipelines. \
You receive verified page element locators and contextual information about a form page. \
Generate structured Playwright test cases.

STRICT RULES:
1. Use ONLY the locators provided in locator_inventory. Never suggest, create, or \
infer locators for elements not explicitly present in the inventory.
2. For every element referenced in test scenarios that does not appear in the inventory, \
add a plain-English description to missing_locators \
(e.g., "phone_field: referenced in test flow but no verified locator found in inventory").
3. When language is "python", generate Python Playwright (pytest) code in playwright_notes. \
When language is "typescript" or not specified, generate TypeScript Playwright code in playwright_notes.
4. When behavioral probe context is provided (probe_outcome is not N/A): use probe \
observations to inform test scenarios \u2014 validation error paths, auth redirect paths, \
success paths.
5. When asset context is provided (test_steps is not N/A): generate playwright_notes \
implementing those specific steps using only the inventory locators.
6. Return ONLY valid JSON matching the schema below. No markdown fences. No preamble.

Output JSON schema:
{
  "test_cases": [
    {
      "id": "string \u2014 [TC-NNN] or [TC-SLUG-NNN]",
      "name": "string",
      "priority": "Critical|High|Medium|Low",
      "category": "Authentication|Form|Navigation|E2E|Accessibility|Grid|Validation|API|Functional|Performance|Negative",
      "description": "string",
      "preconditions": ["string"],
      "steps": [
        {
          "step_number": 1,
          "action": "navigate|fill|click|press|select|assert_url|assert_visible|assert_text|screenshot",
          "target": "string or null",
          "locator": "string (from inventory RECOMMENDED) or null",
          "value": "string or null",
          "description": "string"
        }
      ],
      "locators": {
        "element_name": {
          "primary": "string (from inventory RECOMMENDED verbatim)",
          "fallback": "string or null",
          "strategy": "label|role|testid|text|placeholder|css",
          "locator_type": "label|role|testid|text|placeholder|css",
          "confidence": "high|medium|low"
        }
      },
      "seed_data": {},
      "expected_result": "string",
      "playwright_notes": "string \u2014 complete executable Playwright script using only inventory locators, or null"
    }
  ],
  "missing_locators": ["string \u2014 plain-English description for each missing element"]
}"""

USER_PROMPT_V2 = """\
Page URL: {url}
Page type: {page_type}
Screen key: {screen_key}

Verified locator inventory (use ONLY these locators):
{locator_inventory}

--- Behavioral Probe Context ---
Probe outcome: {probe_outcome}
Error messages observed: {probe_error_messages}
Success indicators observed: {probe_success_indicators}
Fields submitted during probe: {submitted_fields}

--- Test Asset Context ---
Test case ID: {tc_id}
Test steps: {test_steps}
Preconditions: {preconditions}
Expected result: {expected_result}
Output language: {language}

Generate Playwright test cases using ONLY the locators provided in the inventory above."""


def upgrade():
    conn = op.get_bind()
    conn.execute(
        text("""
            UPDATE prompt_templates
            SET
                system_prompt        = :system_prompt,
                user_prompt_template = :user_prompt_template,
                version              = 3,
                ab_variant           = 'inventory'
            WHERE
                service_type     = 'generation'
                AND task         = 'generate_test_cases_with_inventory'
                AND caller_module  = 'playwright_runner'
                AND maturity_level = '*'
                AND is_active    = true
        """),
        {
            "system_prompt":        SYSTEM_PROMPT_V3,
            "user_prompt_template": USER_PROMPT_V3,
        }
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text("""
            UPDATE prompt_templates
            SET
                system_prompt        = :system_prompt,
                user_prompt_template = :user_prompt_template,
                version              = 2
            WHERE
                service_type     = 'generation'
                AND task         = 'generate_test_cases_with_inventory'
                AND caller_module  = 'playwright_runner'
                AND maturity_level = '*'
                AND is_active    = true
        """),
        {
            "system_prompt":        SYSTEM_PROMPT_V2,
            "user_prompt_template": USER_PROMPT_V2,
        }
    )
