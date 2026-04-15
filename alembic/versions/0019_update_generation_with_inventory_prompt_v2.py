"""Update generate_test_cases_with_inventory prompt to version 2 (dual-mode F-03-08/F-03-04)

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-14

ASP-TSCD-001 CHG-03 (amended).
Adds F-03-04 asset context support. Adds language-awareness (typescript/python).
Both F-03-08 and F-03-04 call modes explicitly handled.

I-GATE-01 result: Only one row exists at maturity_level='L2' (migration 016).
No '*' row exists. PAP sends no maturity_level — falls through to wildcard module.
VARIANT B selected: INSERT new row at maturity_level='*' with version 2.

I-GATE-02 result: TestCaseOutput fields confirmed from app/models/generation_outputs.py:
  id, name, priority, category, description, preconditions,
  steps (list[StepOutput]: step_number, action, target, locator, value, description),
  locators (dict[str, LocatorOutput]: primary, fallback, strategy, locator_type, confidence),
  seed_data (dict), expected_result, playwright_notes

Atrium-transition relevance: REPLICATE
"""
from alembic import op
from sqlalchemy import text

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


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
    """VARIANT B: No '*' row exists. Insert new row at maturity_level='*'.

    I-GATE-01 confirmed only one row at maturity_level='L2' (migration 016).
    PAP sends no maturity_level — wildcard resolution needs a '*' row.
    """
    conn = op.get_bind()
    conn.execute(
        text("""
            INSERT INTO prompt_templates
                (service_type, task, caller_module, maturity_level,
                 system_prompt, user_prompt_template, version, is_active)
            VALUES
                ('generation', 'generate_test_cases_with_inventory',
                 'playwright_runner', '*',
                 :system_prompt, :user_prompt_template, 2, true)
            ON CONFLICT (service_type, task, caller_module, maturity_level,
                         version, ab_variant)
            DO UPDATE SET
                system_prompt        = EXCLUDED.system_prompt,
                user_prompt_template = EXCLUDED.user_prompt_template,
                is_active            = true
        """),
        {
            "system_prompt":        SYSTEM_PROMPT_V2,
            "user_prompt_template": USER_PROMPT_V2,
        }
    )


def downgrade():
    """Remove the inserted '*' row. L2 row from migration 016 remains as fallback."""
    conn = op.get_bind()
    conn.execute(
        text("""
            DELETE FROM prompt_templates
            WHERE task            = 'generate_test_cases_with_inventory'
            AND   caller_module   = 'playwright_runner'
            AND   maturity_level  = '*'
            AND   version         = 2
        """)
    )
