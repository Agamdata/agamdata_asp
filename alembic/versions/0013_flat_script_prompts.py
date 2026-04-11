"""Add flat-style script generation prompt templates for TypeScript and Python.

Replaces playwright_typescript_pom and playwright_python_pytest variants
with flat inline variants for all generated scripts. The POM variant rows
inserted by migrations 0004/0005 are kept but no longer called by the
updated script_generator.py.

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-24
"""
from alembic import op
from sqlalchemy import text

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

# ── Shared flat-inline rules prepended to both language prompts ───────────────

FLAT_RULE = '''
SCRIPT STYLE: FLAT INLINE — MANDATORY FOR ALL GENERATED SCRIPTS

DO NOT generate Page Object Model classes, helper methods, or factories.
Every test function MUST be fully self-contained.
All Playwright calls MUST be inline — never via an intermediate method.

CORRECT (flat inline):
  async def test_tc_pi_001(page):                                  # Python
      await page.goto('https://example.com/purchase-invoices/new')
      await page.wait_for_load_state('networkidle')
      await page.get_by_label('Invoice Number').fill('INV-2024-001')
      await page.get_by_role('button', name='Save').click()

  test('[TC-PI-001] Create invoice', async ({ page }) => {         // TypeScript
      await page.goto('https://example.com/purchase-invoices/new');
      await page.waitForLoadState('networkidle');
      await page.getByLabel('Invoice Number').fill('INV-2024-001');
      await page.getByRole('button', { name: 'Save' }).click();
  });

WRONG (never generate this):
  class PurchaseInvoicePage:
      def get_invoice_number(self): return self.page.get_by_label('Invoice Number')
  invoice_page.get_invoice_number().fill('INV-2024-001')  # hides locator

PAGE LOAD RULE:
  Always add wait_for_load_state('networkidle') / waitForLoadState('networkidle')
  immediately after every goto() call and before any element interaction.

LOCATOR RULE:
  Use the locator string from the test case's locators dict exactly as provided.
  Python: page.<<locator>>  where <<locator>> is e.g. get_by_label('Email')
  TypeScript: page.<<locator>>  where <<locator>> is e.g. getByLabel('Email')
  Never construct a new locator string not present in the test case.
'''

# ── Python / pytest system prompt ─────────────────────────────────────────────

PYTHON_SYSTEM = '''\
You generate Playwright Python pytest test scripts.
You receive test cases with verified locators. Your job is to convert them
to working Python test functions.
''' + FLAT_RULE + '''
OUTPUT RULES:
  - One pytest function per test case: def test_<tc_id_lower>_<name_snake>(page):
  - Function name must include the tc_id (e.g. test_tc_pi_001_create_invoice)
  - Imports at top: from playwright.sync_api import Page, expect
  - Use sync_api (not async_api) — pytest-playwright uses sync fixtures
  - All assertions: expect(locator).to_be_visible() / to_have_text() / etc.
  - Return ONLY the Python file content. No markdown. No backticks.
'''

PYTHON_USER = (
    'Generate a flat pytest script for these test cases.\n\n'
    'URL: {url}\n\n'
    'Test cases:\n{test_cases_json}'
)

# ── TypeScript / Playwright Test system prompt ────────────────────────────────

TS_SYSTEM = '''\
You generate Playwright TypeScript test scripts using @playwright/test.
You receive test cases with verified locators. Your job is to convert them
to working TypeScript test functions.
''' + FLAT_RULE + '''
OUTPUT RULES:
  - import {{ test, expect }} from '@playwright/test'; at the top
  - One test() block per test case
  - Test title format: '[TC-XXX-NNN] Test name here'
  - All locators: page.getByLabel() / page.getByRole() / page.locator()
  - All assertions: await expect(locator).toBeVisible() / toHaveText() / etc.
  - Return ONLY the TypeScript file content. No markdown. No backticks.
'''

TS_USER = (
    'Generate a flat Playwright TypeScript test file for these test cases.\n\n'
    'URL: {url}\n\n'
    'Test cases:\n{test_cases_json}'
)

# ── Rows to insert ────────────────────────────────────────────────────────────

ROWS = [
    {
        'svc':     'generation',
        'task':    'generate_playwright_script',
        'mod':     'playwright_runner',
        'mat':     'L2',
        'variant': 'playwright_python_pytest_flat',
        'sys':     PYTHON_SYSTEM,
        'usr':     PYTHON_USER,
    },
    {
        'svc':     'generation',
        'task':    'generate_playwright_script',
        'mod':     'playwright_runner',
        'mat':     'L2',
        'variant': 'playwright_typescript_flat',
        'sys':     TS_SYSTEM,
        'usr':     TS_USER,
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for row in ROWS:
        conn.execute(text('''
            INSERT INTO prompt_templates
                (service_type, task, caller_module, maturity_level,
                 system_prompt, user_prompt_template, ab_variant, is_active)
            VALUES
                (:svc, :task, :mod, :mat, :sys, :usr, :variant, true)
            ON CONFLICT (service_type, task, caller_module, maturity_level,
                         version, ab_variant)
            DO UPDATE SET
                system_prompt        = EXCLUDED.system_prompt,
                user_prompt_template = EXCLUDED.user_prompt_template,
                is_active            = true
        '''), row)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text('''
        DELETE FROM prompt_templates
        WHERE task          = 'generate_playwright_script'
        AND   caller_module = 'playwright_runner'
        AND   ab_variant    IN (
            'playwright_typescript_flat',
            'playwright_python_pytest_flat'
        )
    '''))
