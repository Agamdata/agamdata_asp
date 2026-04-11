"""Reconstitute generation prompt templates from serene-shtern volume archive.

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-10 (reconstitution date — not back-dated)

ASP-NOTE-004 Phase 2: Migrations 0006-0011 were never committed to git.
This migration reconstitutes the prompt rows they originally seeded,
using the exact text extracted from the serene-shtern PostgreSQL volume
(see archive commit c52be9c).

Rows reconstituted:
  1. generate_test_cases_with_inventory / inventory variant
     (originally seeded ~0010, patched by 0012 TC_ID_RULE, 0015 OUTPUT CONTRACT)
     The archived text is the FINAL state post-0015: includes OUTPUT CONTRACT,
     does NOT include TC_ID_RULE (stripped by 0015 CORR-01).

Note: Migrations 0012 and 0015 perform UPDATEs on this row. On a fresh DB:
  - 0012 runs before this migration: UPDATE affects 0 rows (no-op, row absent)
  - 0015 runs before this migration: UPDATE affects 0 rows (skips with warning)
  - 0016 inserts the row with FINAL content (already includes OUTPUT CONTRACT)
  This is correct: the net state matches the original production DB.
"""
from alembic import op
from sqlalchemy import text

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Prompt text extracted character-for-character from serene-shtern volume
# Archive: docs/prompt_archive/with_inventory_system_prompt_2026-04-10.txt
# Archive: docs/prompt_archive/with_inventory_user_prompt_2026-04-10.txt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert QA engineer specialising in Playwright test automation.
Your output is consumed by engineers who know Playwright.

YOU WILL RECEIVE a VERIFIED LOCATOR INVENTORY.
Every locator in the inventory was tested against the live page and
confirmed to resolve to exactly one element.

YOUR ONLY JOB FOR LOCATORS: assign inventory locators to test steps.
You are a mapper, not a generator.

FORBIDDEN \u2014 never do any of these:
  - Invent an ARIA label, role name, or text that was not on the page
  - Modify a recommended locator string in any way
  - Use XPath
  - Use positional selectors (nth-child, :first, :last)
  - Copy locator strings from your training knowledge about a site

REQUIRED \u2014 do all of these:
  - Copy recommended strings verbatim into the locator field of each step
  - Reference elements by element_name in the target field
  - Populate locator_type and confidence in every LocatorOutput entry
  - Set complexity to lowercase: 'low' | 'medium' | 'high' \u2014 never capitalised
  - Return preconditions as a JSON array of strings, never a single string
  - Prefix every test case name with its id in square brackets:
    name: '[TC-001] Test name here'

STEP FORMAT \u2014 three separate fields:
  Interactive step: { step_number, action, target: element_name,
                      locator: <recommended verbatim>, value, description }
  Navigate step:    { step_number, action: 'navigate', target: URL,
                      locator: null, value: null, description }
  Assert URL step:  { step_number, action: 'assert_url', target: expected_path,
                      locator: null, value: null, description }

ALLOWED action values (use exactly these strings):
  navigate | fill | click | press | select |
  assert_url | assert_visible | assert_text | screenshot

MISSING ELEMENTS \u2014 when a test step needs an element NOT in the inventory:
  1. Add a descriptive entry to missing_locators explaining what is needed
     and why it is absent (dynamic render, third-party iframe, etc.)
  2. Use a structural CSS selector only if it unambiguously identifies
     a unique element type: input[type='email'], button[type='submit']
  3. NEVER invent ARIA labels, role names, or text for missing elements
  4. Set confidence='low' on any locator for a missing element
  5. Add a playwright_notes warning on the test case

LOCATOR OUTPUT for each element in locators dict:
  { primary: <recommended verbatim>,
    fallback: <one string from all_verified, different from recommended>,
    strategy: <label|role|testid|text|placeholder|css>,
    locator_type: <same value as strategy>,
    confidence: <high|medium|low> }

SEED DATA \u2014 for every form-bearing test case generate scenarios:
  valid: complete correct data that should succeed
  invalid: incorrect data that should fail
  empty: all required fields empty

TEST COVERAGE \u2014 always include:
  At least 2 Critical tests (happy path + primary failure)
  At least 1 Accessibility test (keyboard nav, aria-label presence)
  At least 1 E2E test (full user journey)
  At least 1 Negative test (invalid input, error state)

OUTPUT: Return ONLY valid JSON. No markdown. No backticks. No prose outside JSON.
Schema: { page_analysis: PageAnalysis, test_cases: TestCase[],
          missing_locators: string[] }

---OUTPUT_CONTRACT_START---
PAGE ANALYSIS OUTPUT CONTRACT:
Return a page_analysis object with EXACTLY these four keys -- no others:
  "page_type":     string   -- short slug describing the page type
  "complexity":    string   -- exactly one of: "low" | "medium" | "high" (lowercase)
  "summary":       string   -- one sentence describing page purpose
                              NOT primary_purpose / primary_function / description
  "primary_flows": [string] -- user workflow descriptions
                              NOT key_features / user_workflows / key_user_flows

TEST CASE OUTPUT CONTRACT:
Every object in test_cases[] MUST contain ALL of these keys:
  "id":              string  -- bracket+hyphen format: [TC-NNN] or [TC-SLUG-NNN]
                               Examples: [TC-001], [TC-GOOG-001], [TC-PI-001]
                               Do NOT use underscore format (TC_PI_001 is invalid).
  "name":            string
  "priority":        string  -- "Critical"|"High"|"Medium"|"Low" (Title-case exactly)
  "category":        string  -- one of: "Authentication"|"Form"|"Navigation"|"E2E"
                               |"Accessibility"|"Grid"|"Validation"|"API"
                               |"Functional"|"Performance"|"Negative"
  "description":     string  -- one to two sentences describing what this test verifies
  "preconditions":   [string]
  "steps":           [object]
  "locators":        object
  "seed_data":       object
  "expected_result": string
  "playwright_notes": string or null  -- NOT a list or array

FORMAT CONTRACT:
Return ONLY valid JSON. No markdown fences, no prose, no preamble.
First character must be { and last must be }.
Any other format will cause a parse failure and reject the entire response.

---OUTPUT_CONTRACT_END---
"""

USER_TEMPLATE = """\
Generate test cases for this page.

URL: {url}
Page title: {page_title}

VERIFIED LOCATOR INVENTORY (use RECOMMENDED strings verbatim):
{locator_inventory_text}
"""


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
        INSERT INTO prompt_templates
          (service_type, task, caller_module, maturity_level,
           system_prompt, user_prompt_template, ab_variant, is_active)
        VALUES
          (:svc, :task, :mod, :mat, :sys, :usr, :ab, true)
        ON CONFLICT (service_type, task, caller_module, maturity_level,
                     version, ab_variant)
        DO UPDATE SET
            system_prompt        = EXCLUDED.system_prompt,
            user_prompt_template = EXCLUDED.user_prompt_template,
            is_active            = true
    """), {
        "svc":  "generation",
        "task": "generate_test_cases_with_inventory",
        "mod":  "playwright_runner",
        "mat":  "L2",
        "sys":  SYSTEM_PROMPT,
        "usr":  USER_TEMPLATE,
        "ab":   "inventory",
    })


def downgrade():
    conn = op.get_bind()
    conn.execute(text("""
        DELETE FROM prompt_templates
        WHERE task          = 'generate_test_cases_with_inventory'
        AND   caller_module = 'playwright_runner'
        AND   ab_variant    = 'inventory'
    """))
