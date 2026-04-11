"""Patch inventory prompt — add TC ID naming rule with sentinel delimiters.

Revision ID: 0012
Revises: 0005 (chain heal — was 0011, see ASP-NOTE-004)
Create Date: 2026-03-24

v1.2 correction C1 applied:
    downgrade() uses [\s\S]*? instead of .*? because PostgreSQL REGEXP_REPLACE
    has no dotall flag — the dot does not match newlines, and TC_ID_RULE_BODY
    contains multiple newline characters. [\s\S]*? matches any character
    including newlines and removes the sentinel block precisely.
"""
from alembic import op
from sqlalchemy import text

revision = '0012'
# Chain heal per ASP-NOTE-004. Original down_revision '0011' referenced a
# migration never committed to git (see archive commit c52be9c).
# Rewritten to close the 0006-0011 gap.
down_revision = '0005'
branch_labels = None
depends_on = None

# Sentinel delimiters — unique strings that will never appear in normal prompt
# text. These bookend the TC ID rule so downgrade() can find and remove it
# precisely regardless of any other changes made to the prompt after 0012 runs.
START_SENTINEL = '---TC_ID_RULE_START---'
END_SENTINEL   = '---TC_ID_RULE_END---'

TC_ID_RULE_BODY = '''
TC ID NAMING RULE — MANDATORY:
  Derive the prefix from the page URL path and page_title, NOT from page_type.

  Rules:
  1. Take the last meaningful path segment of the URL.
     /purchase-invoices  -> PI
     /sales-orders       -> SO
     /customers          -> CUST
     /login or /signin   -> LOGIN
     /dashboard          -> DASH
     /settings           -> SET
  2. If the path segment is ambiguous, use the first 2-4 letters of the
     page_title (cleaned of spaces and special characters).
  3. Format: TC_<PREFIX>_<NNN> with zero-padded 3-digit numbers.
     Examples: TC_PI_001, TC_SO_001, TC_CUST_001
  4. NEVER use TC_LOGIN unless the URL contains 'login', 'signin', or 'auth'
     AND the page_title contains 'Sign In' or 'Login'.
  5. All test cases in one generation share the same prefix.
'''

# Full block that is appended to and removed from the prompt.
TC_ID_BLOCK = f'\n{START_SENTINEL}\n{TC_ID_RULE_BODY}\n{END_SENTINEL}\n'


def upgrade() -> None:
    conn = op.get_bind()
    # Append the sentinel-wrapped block to the existing system_prompt.
    conn.execute(text('''
        UPDATE prompt_templates
        SET system_prompt = system_prompt || :block
        WHERE task          = 'generate_test_cases_with_inventory'
        AND   caller_module = 'playwright_runner'
    '''), {'block': TC_ID_BLOCK})


def downgrade() -> None:
    conn = op.get_bind()
    # Remove the sentinel-wrapped block using REGEXP_REPLACE.
    # [\s\S]*? matches any character INCLUDING newlines.
    # This is required because PostgreSQL REGEXP_REPLACE has no dotall (s) flag
    # and TC_ID_RULE_BODY contains multiple newline characters.
    conn.execute(text(r'''
        UPDATE prompt_templates
        SET system_prompt = REGEXP_REPLACE(
            system_prompt,
            '\n---TC_ID_RULE_START---[\s\S]*?---TC_ID_RULE_END---\n',
            '',
            'g'
        )
        WHERE task          = 'generate_test_cases_with_inventory'
        AND   caller_module = 'playwright_runner'
    '''))
