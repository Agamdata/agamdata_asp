"""ASP-FEAT-ASP-03 v2.0 — prompt-only migration.

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-18

Five operations in exact order:
  1. Deactivate v3 canonical row (e6c88ca5) for generate_test_cases_with_inventory
  2. Deactivate v1 L2-override row (e92c4809)
  3. Insert v4 playwright_runner row (serves F-03-08 batch + F-03-04 single-TC)
  4. Insert v4 test_generator row    (serves F-01-10 interactive live panel)
  5. Insert v1 row for refactor_script_locators (new task)

All text prompts use explicit shared-fragment markers
  <!-- SHARED_FRAGMENT: <NAME> -->
so AC-SHARED-01 (post-migration SQL + difflib.ndiff) can diff the four
governed fragments between ops 3 and 4 and assert byte-for-byte identity.

Prompt content locked at ASP-OUT-012 v4 prompt content ruling
(Principal Architect, 2026-04-18).

Downgrade reverses in exact opposite order: delete the three new INSERTs,
then reactivate the v1 L2-override row, then reactivate the v3 canonical
row. The text of the pre-existing rows is never touched (only is_active
flips), so no text restoration is required.

Note on rule numbering: Q1 in ASP-OUT-012 said "Add new rules as 6, 7, 8
in order" but concrete content was provided only for Rules 6
(CATEGORIES_SCHEMA) and 7 (LOCATOR_SOURCE_BRANCH). FORM_DATA_BLOCK
landed in the user-prompt (not a system-prompt rule). Rule 8 was not
materialised; Dev Team proceeded with 6, 7, and (for the test_generator
row only) 9 per the directive's Q3 text. Flagged in the DEV-IN-012
milestone report for Architect confirmation; easily amended if a
concrete Rule 8 is later supplied.
"""
from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# SHARED FRAGMENTS — identical text required in both v4 rows (AC-SHARED-01)
# ---------------------------------------------------------------------------

OUTPUT_CONTRACT_V3 = """\
Output JSON schema — follow exactly:
<!-- SHARED_FRAGMENT: OUTPUT_CONTRACT_V3 -->
{
  "test_cases": [
    {
      "name": "string — descriptive test case name",
      "priority": "Critical|High|Medium|Low",
      "category": "string — e.g. Form|Navigation|Validation|Authentication",
      "description": "string — what this test case verifies",
      "preconditions": ["string — prerequisite condition"],
      "steps": [
        {
          "step_number": 1,
          "action": "fill|click|navigate|assert|select|hover",
          "locator": "string — exact locator from inventory",
          "value": "string or null",
          "description": "string — plain English step description"
        }
      ],
      "expected_result": "string — what a passing test looks like"
    }
  ],
  "missing_locators": ["string — element name: reason not found in inventory"],
  "covered_categories": ["string — category names from categories_to_generate that were generated in this response"]
}
<!-- /SHARED_FRAGMENT: OUTPUT_CONTRACT_V3 -->"""


CATEGORIES_SCHEMA_RULE_6 = """\
<!-- SHARED_FRAGMENT: CATEGORIES_SCHEMA -->
6. COVERAGE-AWARE GENERATION:
   When categories_to_generate is provided, generate ONLY test cases for
   the listed categories. Do not generate test cases for any other category.
   When categories_to_generate is absent, generate the standard five
   categories: happy_path, required_field_validation, invalid_data_format,
   boundary_values, unauthorised_access.
   Always populate covered_categories in the response with the categories
   you actually generated.
<!-- /SHARED_FRAGMENT: CATEGORIES_SCHEMA -->"""


LOCATOR_SOURCE_BRANCH_RULE_7 = """\
<!-- SHARED_FRAGMENT: LOCATOR_SOURCE_BRANCH -->
7. LOCATOR SOURCE QUALITY:
   When locator_source is "verified": treat every locator in the inventory
   as confirmed and reliable. Use them with full confidence.
   When locator_source is "live_extracted": treat inventory locators as
   best-effort. Prefer role, label, and data-testid selectors over CSS
   class or positional selectors. For any locator that appears fragile or
   ambiguous, add it to missing_locators with a note: "live-extracted
   locator — verify before committing to test suite."
<!-- /SHARED_FRAGMENT: LOCATOR_SOURCE_BRANCH -->"""


# ---------------------------------------------------------------------------
# ROW-SPECIFIC: test_generator interactive rule (RULE 9)
# ---------------------------------------------------------------------------

INTERACTIVE_RULE_9 = """\
9. This is an interactive panel call. Generate between 1 and 3 test cases
   only. The engineer reviews output immediately — comprehensive coverage
   is NOT required. Prioritise the most valuable scenario for the page
   type and available locators."""


# ---------------------------------------------------------------------------
# v3 BASE — STRICT RULES 1-5 and preamble (verbatim from migration 020)
# ---------------------------------------------------------------------------

V3_PREAMBLE = """\
You are a Playwright test case generator for automated testing pipelines.
You receive verified page element locators and contextual information about a form page.
Generate structured test cases using ONLY the locators provided in the input."""


V3_RULES_1_TO_5 = """\
STRICT RULES:
1. Use ONLY locators from locator_inventory. Never suggest, infer, or create locators
   for elements not in the inventory.
2. For every element referenced in test steps that does not appear in the inventory,
   add a plain-English description to missing_locators.
   Example: "phone_field: referenced in test flow but no verified locator in inventory"
3. Generate test cases for the scenario described in the GENERATION INSTRUCTIONS
   section of the user message. Follow the mode and focus area specified there.
4. Every step locator string must exactly match a locator value from the input
   locator_inventory. Do not paraphrase or abbreviate locator strings.
5. Return ONLY valid JSON matching the schema below.
   No markdown fences. No preamble. No explanation outside the JSON."""


# ---------------------------------------------------------------------------
# ASSEMBLED SYSTEM PROMPTS
# ---------------------------------------------------------------------------

V4_PLAYWRIGHT_RUNNER_SYSTEM_PROMPT = "\n\n".join([
    V3_PREAMBLE,
    V3_RULES_1_TO_5,
    CATEGORIES_SCHEMA_RULE_6,
    LOCATOR_SOURCE_BRANCH_RULE_7,
    OUTPUT_CONTRACT_V3,
])


V4_TEST_GENERATOR_SYSTEM_PROMPT = "\n\n".join([
    V3_PREAMBLE,
    V3_RULES_1_TO_5,
    CATEGORIES_SCHEMA_RULE_6,
    LOCATOR_SOURCE_BRANCH_RULE_7,
    INTERACTIVE_RULE_9,
    OUTPUT_CONTRACT_V3,
])


# ---------------------------------------------------------------------------
# ASSEMBLED USER PROMPT TEMPLATE (shared between both v4 rows)
# ---------------------------------------------------------------------------

V4_SHARED_USER_PROMPT_TEMPLATE = """\
Page URL: {url}
Page type: {page_type}
Screen key: {screen_key}

Verified locator inventory — use ONLY these locators in step locator fields:
{locator_inventory}

<!-- SHARED_FRAGMENT: FORM_DATA_BLOCK -->
--- Form Data Context ---
{form_data_context}
<!-- /SHARED_FRAGMENT: FORM_DATA_BLOCK -->

--- Generation Instructions ---
{generation_instructions}

--- Behavioral Probe Context ---
{probe_context}

Generate test cases now."""


# ---------------------------------------------------------------------------
# REFACTOR_SCRIPT_LOCATORS v1 PROMPT (from ASP-OUT-012 verbatim)
# ---------------------------------------------------------------------------

REFACTOR_SYSTEM_PROMPT = """\
You are a Playwright script refactoring assistant. You receive an existing
test script and a list of locator changes. Update the script to use the new
locators while preserving all test logic exactly.

STRICT RULES:
1. Replace ONLY the locators listed in locator_diff. Do not modify any other
   part of the script.
2. Preserve test logic, assertions, and step ordering exactly.
3. For each change in locator_diff, record the element_name in changes_made.
4. If a locator in locator_diff does not appear in the script, add it to
   unchanged_locators with note: "not found in script."
5. Populate warnings for any change where the old_locator appears more than
   once in the script — multiple replacements may affect different logical
   steps.
6. Return ONLY valid JSON. No markdown fences. No preamble.

Output JSON schema:
{
  "refactored_script": "string — full updated script body",
  "changes_made": ["string — element_name: brief description of change"],
  "unchanged_locators": ["string — element_name: reason"],
  "warnings": ["string — warning message"]
}"""


REFACTOR_USER_PROMPT_TEMPLATE = """\
Script to refactor:
{script_body}

Locator changes to apply:
{locator_diff}

Screen key: {screen_key}
Language: {language}

Apply the locator changes now."""


# ---------------------------------------------------------------------------
# Migration operations
# ---------------------------------------------------------------------------

def upgrade():
    # Op 1 — deactivate v3 canonical row
    op.execute("""
        UPDATE prompt_templates
        SET is_active = FALSE
        WHERE id = 'e6c88ca5-1caa-4025-b3b1-450c356cb561'
          AND service_type = 'generation'
          AND task = 'generate_test_cases_with_inventory';
    """)

    # Op 2 — deactivate v1 L2-override row
    op.execute("""
        UPDATE prompt_templates
        SET is_active = FALSE
        WHERE id = 'e92c4809-3308-4b0c-aeb5-d23e4895b882'
          AND service_type = 'generation'
          AND task = 'generate_test_cases_with_inventory';
    """)

    # Op 3 — insert v4 playwright_runner row (F-03-08 + F-03-04)
    op.execute(
        sa.text("""
            INSERT INTO prompt_templates
              (service_type, task, caller_module, maturity_level, version,
               is_active, ab_variant, system_prompt, user_prompt_template)
            VALUES
              ('generation', 'generate_test_cases_with_inventory',
               'playwright_runner', '*', 4, TRUE, 'inventory',
               :sys, :usr)
        """).bindparams(
            sys=V4_PLAYWRIGHT_RUNNER_SYSTEM_PROMPT,
            usr=V4_SHARED_USER_PROMPT_TEMPLATE,
        )
    )

    # Op 4 — insert v4 test_generator row (F-01-10 interactive)
    op.execute(
        sa.text("""
            INSERT INTO prompt_templates
              (service_type, task, caller_module, maturity_level, version,
               is_active, ab_variant, system_prompt, user_prompt_template)
            VALUES
              ('generation', 'generate_test_cases_with_inventory',
               'test_generator', '*', 4, TRUE, 'inventory',
               :sys, :usr)
        """).bindparams(
            sys=V4_TEST_GENERATOR_SYSTEM_PROMPT,
            usr=V4_SHARED_USER_PROMPT_TEMPLATE,
        )
    )

    # Op 5 — seed refactor_script_locators v1 row
    op.execute(
        sa.text("""
            INSERT INTO prompt_templates
              (service_type, task, caller_module, maturity_level, version,
               is_active, ab_variant, system_prompt, user_prompt_template)
            VALUES
              ('generation', 'refactor_script_locators',
               'playwright_runner', '*', 1, TRUE, NULL,
               :sys, :usr)
        """).bindparams(
            sys=REFACTOR_SYSTEM_PROMPT,
            usr=REFACTOR_USER_PROMPT_TEMPLATE,
        )
    )


def downgrade():
    # Reverse order:
    # (a) DELETE the three new INSERTs (ops 5, 4, 3)
    # (b) Reactivate v1 L2-override row (op 2 reverse)
    # (c) Reactivate v3 canonical row (op 1 reverse)
    # Text of pre-existing rows was never modified by upgrade — only is_active
    # flipped, so no text restoration is required.

    # Delete refactor_script_locators v1 row
    op.execute("""
        DELETE FROM prompt_templates
        WHERE service_type = 'generation'
          AND task = 'refactor_script_locators'
          AND version = 1
          AND caller_module = 'playwright_runner';
    """)

    # Delete both v4 rows (playwright_runner + test_generator)
    op.execute("""
        DELETE FROM prompt_templates
        WHERE service_type = 'generation'
          AND task = 'generate_test_cases_with_inventory'
          AND version = 4
          AND caller_module IN ('playwright_runner', 'test_generator');
    """)

    # Reactivate v1 L2-override row
    op.execute("""
        UPDATE prompt_templates
        SET is_active = TRUE
        WHERE id = 'e92c4809-3308-4b0c-aeb5-d23e4895b882';
    """)

    # Reactivate v3 canonical row
    op.execute("""
        UPDATE prompt_templates
        SET is_active = TRUE
        WHERE id = 'e6c88ca5-1caa-4025-b3b1-450c356cb561';
    """)
