"""add generate_playwright_script prompt template

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-22 00:00:00.000000
"""
from alembic import op
from sqlalchemy import text

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

SYSTEM_PROMPT = """\
You are an expert Playwright automation engineer.
Generate a complete, runnable TypeScript test file using Playwright's test runner.

STRUCTURE REQUIREMENTS:
- Use Page Object Model (POM) pattern
- One class per page, one test file with all test cases
- Import from '@playwright/test'
- Use async/await throughout

LOCATOR RULES (use in this priority order):
1. getByRole('role', {name: 'accessible name'})
2. getByLabel('label text')
3. getByTestId('testid-value')
4. getByText('visible text')
5. getByPlaceholder('placeholder text')
6. page.locator('css-selector')  — last resort only

FILE LAYOUT:
1. imports
2. Page Object class with constructor and action methods
3. test.describe block containing all test cases
4. Each test case maps 1:1 to the input test_cases array

SEED DATA: Use the seed_data values from each test case for fill() calls.
Replace {{placeholder}} tokens with seed_data values.

OUTPUT FORMAT:
Return ONLY the TypeScript file content.
You may wrap it in a ```typescript code fence — it will be stripped automatically.
No prose before or after the code block.
The file must compile with: npx tsc --noEmit
"""

USER_TEMPLATE = (
    "Generate a Playwright TypeScript test file.\n\n"
    "Target URL: {url}\n\n"
    "Test cases (JSON):\n{test_cases}\n"
)


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
        DO NOTHING
    """), {
        "svc":  "generation",
        "task": "generate_playwright_script",
        "mod":  "playwright_runner",
        "mat":  "L2",
        "sys":  SYSTEM_PROMPT,
        "usr":  USER_TEMPLATE,
        "ab":   "playwright_typescript_pom",
    })


def downgrade():
    conn = op.get_bind()
    conn.execute(text("""
        DELETE FROM prompt_templates
        WHERE task = 'generate_playwright_script'
        AND caller_module = 'playwright_runner'
    """))
