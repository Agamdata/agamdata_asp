"""Elevate test case count enforcement to system prompt — hard constraint framing

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-16

AC-020-02 FAIL: LLM generates 5 TCs when instructed to generate 1.
Root cause: count instruction in user prompt {generation_instructions} treated
as context, not constraint. Fix: reframe as hard caller-enforced schema rule
in system prompt Rule 3.

Principal Architect ruling: "The fix is not stronger wording in the same location.
The fix is moving the structural constraint to the right layer."
"""
from alembic import op
from sqlalchemy import text

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

OLD_RULE_3 = """\
3. Generate the number of test cases specified in the generation instructions below.
   Do not exceed the specified count."""

NEW_RULE_3 = """\
3. TEST CASE COUNT IS A HARD LIMIT SET BY THE CALLER.
   The GENERATION INSTRUCTIONS section of the user message specifies
   the exact number of test cases to generate.
   - If it says EXACTLY ONE: return exactly one test case. No more.
   - If it says EXACTLY FIVE: return exactly five test cases. No more, no fewer.
   Generating a different count is a schema violation. The caller's system
   validates count strictly and will reject responses that do not match.
   The count instruction overrides any judgment about how many test cases
   would be "useful" or "thorough.\""""


def upgrade():
    conn = op.get_bind()
    # Read current system_prompt
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
        raise RuntimeError("0021: prompt row not found for with_inventory / * / inventory")

    current_prompt = row[0]
    if OLD_RULE_3 not in current_prompt:
        raise RuntimeError(
            "0021: Expected Rule 3 text not found in current system_prompt. "
            "Cannot safely replace. Manual intervention required."
        )

    updated_prompt = current_prompt.replace(OLD_RULE_3, NEW_RULE_3)

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
        {"prompt": updated_prompt}
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
    if row is None:
        return

    current_prompt = row[0]
    if NEW_RULE_3 in current_prompt:
        reverted_prompt = current_prompt.replace(NEW_RULE_3, OLD_RULE_3)
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
            {"prompt": reverted_prompt}
        )
