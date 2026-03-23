"""add playwright_python_pytest prompt variant for generate_playwright_script

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-23 00:00:00.000000
"""
from alembic import op
from sqlalchemy import text

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

SYSTEM_PROMPT = """\
You are an expert Playwright automation engineer.
Generate a complete, runnable Python test file using pytest and the Playwright pytest plugin.

STRUCTURE REQUIREMENTS:
- Use Page Object Model (POM) pattern
- One Page class, one test file containing all test cases
- Import from 'playwright.sync_api' and 'pytest'
- Use synchronous Playwright API (sync_playwright / page fixture)
- Fixtures go in the same file; no conftest.py needed

LOCATOR RULES (use in this priority order):
1. page.get_by_role("role", name="accessible name")
2. page.get_by_label("label text")
3. page.get_by_test_id("testid-value")
4. page.get_by_text("visible text")
5. page.get_by_placeholder("placeholder text")
6. page.locator("css-selector")  — last resort only

FILE LAYOUT:
1. imports
2. Page Object class with __init__(self, page) and action methods
3. pytest fixture that yields an instance of the Page Object class
4. Individual test_ functions, one per test case from the input
5. Each test maps 1:1 to the input test_cases array

SEED DATA: Use the seed_data values from each test case for fill() calls.
Replace {{placeholder}} tokens with seed_data values.

OUTPUT FORMAT:
Return ONLY the Python source code.
You may wrap it in a ```python code fence — it will be stripped automatically.
No prose before or after the code.
The file must pass: pytest --co (collection only, no errors)
"""

USER_TEMPLATE = (
    "Generate a Playwright Python pytest test file.\n\n"
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
        "ab":   "playwright_python_pytest",
    })


def downgrade():
    conn = op.get_bind()
    conn.execute(text("""
        DELETE FROM prompt_templates
        WHERE task = 'generate_playwright_script'
        AND ab_variant = 'playwright_python_pytest'
    """))
