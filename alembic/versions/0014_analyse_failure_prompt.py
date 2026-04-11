"""Add analyse_failure prompt template for playwright_runner.

Seeds both system_prompt and user_prompt_template so handle_analyse_failure()
in nlp.py can fetch both from the registry — no hardcoded prompt strings in
the service layer.

USER_TEMPLATE uses the expanded key set from v1.1 R2:
    tc_id, test_name, page_url, error_message, stack_trace,
    locators_json, steps_json

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-24
"""
from alembic import op
from sqlalchemy import text

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None

SYSTEM_PROMPT = '''\
You are an expert Playwright test engineer analysing why a test failed.
You receive the error message, stack trace, locators used, and test steps.

YOUR TASK: identify the root cause and provide a specific, actionable fix.

ROOT CAUSE CATEGORIES — use exactly one of these strings:
  LOCATOR_NOT_FOUND   — element not found on page (TimeoutError on locator)
  TIMEOUT             — page or action took too long (non-locator timeout)
  ASSERTION_FAILED    — expect() assertion did not match
  NAVIGATION_FAILED   — page.goto() failed or redirected unexpectedly
  ELEMENT_NOT_VISIBLE — element exists but is hidden or off-screen
  AUTH_REQUIRED       — page redirected to login; test ran without auth
  NETWORK_ERROR       — request failed, ERR_NAME_NOT_RESOLVED, etc.
  UNKNOWN             — insufficient information to categorise

FOR LOCATOR_NOT_FOUND or ELEMENT_NOT_VISIBLE:
  - Look at the locator strings provided in LOCATORS USED IN TEST
  - If the locator uses CSS (locator('...')), suggest a semantic alternative
  - If the error shows a different element name, suggest that as updated_locator
  - Always provide an updated_locator value if derivable from the evidence

FOR AUTH_REQUIRED:
  - updated_locator is not applicable — set to null
  - fix_suggestion must explain that credentials/auth setup are needed

CONFIDENCE RULES:
  high   — TimeoutError with locator shown + error is unambiguous
  medium — error points to likely cause but context is incomplete
  low    — only generic error, no stack trace, cannot determine cause

OUTPUT: Return ONLY valid JSON. No markdown. No backticks.
Schema:
{
  "root_cause": "string",
  "root_cause_category": "string",
  "fix_suggestion": "string",
  "updated_locator": "string | null",
  "confidence": "high | medium | low"
}
'''

# v1.1 R2 expanded USER_TEMPLATE — includes locators_json and steps_json so
# handle_analyse_failure() does not need to assemble the message inline.
USER_TEMPLATE = (
    'Analyse this Playwright test failure.\n\n'
    'Test: {tc_id} — {test_name}\n'
    'Page URL: {page_url}\n\n'
    'ERROR:\n{error_message}\n\n'
    'STACK TRACE:\n{stack_trace}\n\n'
    'LOCATORS USED IN TEST:\n{locators_json}\n\n'
    'TEST STEPS:\n{steps_json}'
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text('''
        INSERT INTO prompt_templates
            (service_type, task, caller_module, maturity_level,
             system_prompt, user_prompt_template, is_active)
        VALUES (:svc, :task, :mod, :mat, :sys, :usr, true)
        ON CONFLICT (service_type, task, caller_module, maturity_level,
                     version, ab_variant)
        DO UPDATE SET
            system_prompt        = EXCLUDED.system_prompt,
            user_prompt_template = EXCLUDED.user_prompt_template,
            is_active            = true
    '''), {
        'svc':  'nlp',
        'task': 'analyse_failure',
        'mod':  'playwright_runner',
        'mat':  'L2',
        'sys':  SYSTEM_PROMPT,
        'usr':  USER_TEMPLATE,
    })


def downgrade() -> None:
    op.get_bind().execute(text('''
        DELETE FROM prompt_templates
        WHERE task          = 'analyse_failure'
        AND   caller_module = 'playwright_runner'
    '''))
