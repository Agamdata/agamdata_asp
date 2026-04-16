"""Replace Rule 3 hard-constraint framing with neutral wording

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-16

Principal Architect ruling: LLM count instructions are unreliable regardless
of framing. Count enforcement moves to handler post-processing.
Rule 3 reverts to honest neutral wording. The handler enforces count.
"""
from alembic import op
from sqlalchemy import text

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

OLD_RULE_3 = """\
3. TEST CASE COUNT IS A HARD LIMIT SET BY THE CALLER.
   The GENERATION INSTRUCTIONS section of the user message specifies
   the exact number of test cases to generate.
   - If it says EXACTLY ONE: return exactly one test case. No more.
   - If it says EXACTLY FIVE: return exactly five test cases. No more, no fewer.
   Generating a different count is a schema violation. The caller's system
   validates count strictly and will reject responses that do not match.
   The count instruction overrides any judgment about how many test cases
   would be "useful" or "thorough.\""""

NEW_RULE_3 = """\
3. Generate test cases for the scenario described in the GENERATION INSTRUCTIONS
   section of the user message. Follow the mode and focus area specified there."""


def upgrade():
    conn = op.get_bind()
    result = conn.execute(
        text("""
            SELECT system_prompt FROM prompt_templates
            WHERE task = 'generate_test_cases_with_inventory'
            AND caller_module = 'playwright_runner'
            AND maturity_level = '*'
            AND ab_variant = 'inventory'
            AND is_active = true
        """)
    )
    row = result.fetchone()
    if row is None:
        raise RuntimeError("0022: prompt row not found")

    current = row[0]
    if OLD_RULE_3 not in current:
        raise RuntimeError("0022: Expected Rule 3 (hard-constraint) not found in prompt")

    updated = current.replace(OLD_RULE_3, NEW_RULE_3)
    conn.execute(
        text("""
            UPDATE prompt_templates
            SET system_prompt = :prompt
            WHERE task = 'generate_test_cases_with_inventory'
            AND caller_module = 'playwright_runner'
            AND maturity_level = '*'
            AND ab_variant = 'inventory'
            AND is_active = true
        """),
        {"prompt": updated}
    )


def downgrade():
    conn = op.get_bind()
    result = conn.execute(
        text("""
            SELECT system_prompt FROM prompt_templates
            WHERE task = 'generate_test_cases_with_inventory'
            AND caller_module = 'playwright_runner'
            AND maturity_level = '*'
            AND ab_variant = 'inventory'
            AND is_active = true
        """)
    )
    row = result.fetchone()
    if row and NEW_RULE_3 in row[0]:
        reverted = row[0].replace(NEW_RULE_3, OLD_RULE_3)
        conn.execute(
            text("""
                UPDATE prompt_templates
                SET system_prompt = :prompt
                WHERE task = 'generate_test_cases_with_inventory'
                AND caller_module = 'playwright_runner'
                AND maturity_level = '*'
                AND ab_variant = 'inventory'
                AND is_active = true
            """),
            {"prompt": reverted}
        )
