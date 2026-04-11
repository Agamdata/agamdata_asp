"""Patch python_playwright_pytest_flat prompt — ban lambda in expect() assertions.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-11

ASP-FEAT-ASP-03 v1.1 — folds DEFECT-006.
PAP reported generated Python scripts use lambda in expect().to_have_url()
which crashes at runtime. Playwright assertion API only accepts str or re.Pattern.

Appends a sentinel-delimited ASSERTION RULE block to the system prompt:
1. NEVER use lambda inside expect() assertions.
2. Required import: import re.
3. Example: expect(page).to_have_url(re.compile(r"q=Playwright")).
4. No markdown fences in output.
"""
from alembic import op
from sqlalchemy import text

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

START_SENTINEL = "---ASSERTION_RULE_START---"
END_SENTINEL = "---ASSERTION_RULE_END---"

ASSERTION_RULE = """\
ASSERTION RULE — MANDATORY FOR ALL PYTHON SCRIPTS:
  NEVER use lambda inside expect() assertions.
  Playwright's assertion API accepts ONLY str or re.Pattern — not callables.

  WRONG (will crash):
    expect(page).to_have_url(lambda url: "search" in url)

  CORRECT:
    expect(page).to_have_url(re.compile(r"search"))

  REQUIRED: Add 'import re' at top of file when ANY assertion uses re.compile().

  For partial URL matching: expect(page).to_have_url(re.compile(r"q=Playwright"))
  For partial text matching: expect(locator).to_have_text(re.compile(r"Success"))
  For exact matching: expect(page).to_have_url("https://example.com/leads")

  No markdown fences in output. Return ONLY the Python file content.
"""

BLOCK = f"\n{START_SENTINEL}\n{ASSERTION_RULE}\n{END_SENTINEL}\n"


def upgrade():
    conn = op.get_bind()
    # Append to python flat variant
    conn.execute(text("""
        UPDATE prompt_templates
        SET system_prompt = system_prompt || :block
        WHERE task          = 'generate_playwright_script'
        AND   caller_module = 'playwright_runner'
        AND   ab_variant    = 'playwright_python_pytest_flat'
    """), {"block": BLOCK})

    # Also append to the original (non-flat) Python variant for coverage
    conn.execute(text("""
        UPDATE prompt_templates
        SET system_prompt = system_prompt || :block
        WHERE task          = 'generate_playwright_script'
        AND   caller_module = 'playwright_runner'
        AND   ab_variant    = 'playwright_python_pytest'
    """), {"block": BLOCK})


def downgrade():
    conn = op.get_bind()
    conn.execute(text(r"""
        UPDATE prompt_templates
        SET system_prompt = REGEXP_REPLACE(
            system_prompt,
            '\n---ASSERTION_RULE_START---[\s\S]*?---ASSERTION_RULE_END---\n',
            '', 'g'
        )
        WHERE task          = 'generate_playwright_script'
        AND   caller_module = 'playwright_runner'
        AND   ab_variant    IN ('playwright_python_pytest_flat', 'playwright_python_pytest')
    """))
