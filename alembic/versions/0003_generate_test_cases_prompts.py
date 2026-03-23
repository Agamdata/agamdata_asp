"""add generate_test_cases prompt templates

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-22 00:00:00.000000
"""
from alembic import op
from sqlalchemy import text

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SYSTEM_PROMPT = """\
You are an expert QA engineer specialising in Playwright test automation.
Your output is consumed by engineers who know Playwright — use precise technical terms.

LOCATOR PRIORITY — generate in this strict order, stop at first that applies:
1. getByRole('role', {name: 'accessible name'})  — semantic HTML or role= attr
2. getByLabel('label text')                       — input has associated label
3. getByTestId('testid-value')                    — data-testid attr present
4. getByText('visible text')                      — unique visible text
5. getByPlaceholder('placeholder text')           — input has placeholder
6. page.locator('css-selector')                   — LAST RESORT only.
   When using level 6: set strategy to 'css-fallback — add data-testid'.

SEED DATA — for every form-bearing test case generate these scenarios:
  valid: complete correct data that should succeed
  invalid_empty: all required fields empty
  invalid_format: correct structure but malformed values (bad email, short password)
  boundary: values at max/min length limits

TEST CASE COVERAGE — always include:
  - At least 2 Critical tests (happy path + primary failure)
  - At least 1 Accessibility test (keyboard navigation, aria-label presence)
  - At least 1 E2E test (full user journey across multiple steps)
  - At least 1 Negative test (invalid input, error state validation)

STEP ACTIONS — use only these action values:
  navigate | fill | click | press | select |
  expect_visible | expect_text | expect_url | screenshot

OUTPUT FORMAT:
Return ONLY valid JSON. No markdown. No backticks. No prose outside the JSON.
STRICT LIMITS to keep response small:
- Generate exactly 3 test cases (no more).
- Maximum 4 steps per test case.
- seed_data: include only "valid" and "invalid_format" scenarios, values under 30 chars. Never use code expressions like "a".repeat(255) — use literal strings only.
- All string values under 100 characters. No multi-sentence descriptions.
- locators: primary only (omit fallback unless critical). strategy max 5 words.
Do NOT escape apostrophes. Use plain single quotes inside strings: getByRole('button').
Outer schema: { page_analysis: PageAnalysis, test_cases: TestCase[] }
PageAnalysis schema:
{ page_type: string, complexity: 'low'|'medium'|'high',
  summary: string, primary_flows: string[],
  detected_elements: string[], tech_stack_hints: string[] }
TestCase schema:
{ id: string, name: string,
  priority: 'Critical'|'High'|'Medium'|'Low',
  category: string, description: string, preconditions: string,
  steps: Step[], locators: {name: Locator}, seed_data: {}, expected_result: string,
  playwright_notes: string|null }
Step schema:
{ step_number: int, action: string, target: string|null,
  value: string|null, description: string }
Locator schema:
{ primary: string, fallback: string|null, strategy: string }
"""

USER_TEMPLATE_SNAPSHOT = (
    "Analyse this page and generate test cases.\n\n"
    "URL: {url}\n"
    "Page title: {page_title}\n\n"
    "ACCESSIBILITY TREE (from live page — use these exact names and roles):\n"
    "{snapshot_text}\n\n"
    "INTERACTIVE ELEMENTS INVENTORY (structured):\n"
    "{interactive_elements}\n"
)

USER_TEMPLATE_INFERRED = (
    "Analyse this page and generate test cases.\n"
    "You have not seen the live page HTML — infer from URL and page type.\n\n"
    "URL: {url}\n"
    "Page title: {page_title}\n"
)


def upgrade():
    conn = op.get_bind()

    # Row 1: snapshot variant
    conn.execute(text("""
        INSERT INTO prompt_templates
          (service_type, task, caller_module, maturity_level,
           system_prompt, user_prompt_template, ab_variant, is_active)
        VALUES
          (:svc, :task, :mod, :mat, :sys, :usr, :ab, true)
        ON CONFLICT (service_type, task, caller_module, maturity_level,
                     version, ab_variant)
        DO NOTHING
    """), {
        "svc":  "generation",
        "task": "generate_test_cases",
        "mod":  "playwright_runner",
        "mat":  "L2",
        "sys":  SYSTEM_PROMPT,
        "usr":  USER_TEMPLATE_SNAPSHOT,
        "ab":   "snapshot",
    })

    # Row 2: inferred variant (fallback when no snapshot available)
    conn.execute(text("""
        INSERT INTO prompt_templates
          (service_type, task, caller_module, maturity_level,
           system_prompt, user_prompt_template, ab_variant, is_active)
        VALUES
          (:svc, :task, :mod, :mat, :sys, :usr, :ab, true)
        ON CONFLICT (service_type, task, caller_module, maturity_level,
                     version, ab_variant)
        DO NOTHING
    """), {
        "svc":  "generation",
        "task": "generate_test_cases",
        "mod":  "playwright_runner",
        "mat":  "L2",
        "sys":  SYSTEM_PROMPT,
        "usr":  USER_TEMPLATE_INFERRED,
        "ab":   "inferred",
    })


def downgrade():
    conn = op.get_bind()
    conn.execute(text("""
        DELETE FROM prompt_templates
        WHERE task = 'generate_test_cases'
        AND caller_module = 'playwright_runner'
    """))
