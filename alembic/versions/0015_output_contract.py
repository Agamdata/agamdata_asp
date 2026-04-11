"""Append OUTPUT CONTRACT block to all three test-case generation prompt rows.

Revision ID: 0015
Revises:     0014
Create Date: 2026-03-24

Applies to tasks:
  - generate_test_cases_with_inventory  (single-screen inventory)
  - generate_test_cases_deep_dive       (multi-screen ScreenDeepDiver) -- skipped if row absent
  - generate_test_cases                 (snapshot fallback)

CORR-01 (PAP-TSCD-005 v1.1):
    upgrade() strips the 0012 TC_ID_RULE block from
    generate_test_cases_with_inventory BEFORE appending the OUTPUT CONTRACT.
    Without this, both blocks exist simultaneously in the prompt and give
    contradictory tc_id format instructions (underscore vs bracket+hyphen).
    downgrade() re-appends the TC_ID_RULE block if it is no longer present.

CORR-02 (PAP-TSCD-005 v1.1):
    All REGEXP_REPLACE calls use raw r-strings and [\s\S]*? to match any
    character including newlines. PAP-TSCD-005 v1.0 contained a corrupted
    character class (backslashes stripped by the Word processor) that only
    matched the literal characters s and S, silently leaving the block in
    place. This file uses the correct dotall-safe pattern throughout.

CORR-05 (PAP-TSCD-005 v1.1):
    imports are at module top, not inside function bodies.
"""
import warnings

from alembic import op
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------
revision      = '0015'
down_revision = '0014'
branch_labels = None
depends_on    = None

# ---------------------------------------------------------------------------
# OUTPUT CONTRACT sentinels (unique to this migration)
# ---------------------------------------------------------------------------
START_SENTINEL = '---OUTPUT_CONTRACT_START---'
END_SENTINEL   = '---OUTPUT_CONTRACT_END---'

# ---------------------------------------------------------------------------
# 0012 TC_ID_RULE sentinels — used in upgrade() to remove the conflicting block
# and in downgrade() to restore it.
# ---------------------------------------------------------------------------
TC_RULE_START = '---TC_ID_RULE_START---'
TC_RULE_END   = '---TC_ID_RULE_END---'

# Duplicate of the TC_ID_RULE_BODY from migration 0012.
# Used in downgrade() to restore the block that upgrade() removed.
# Must be kept in sync with 0012_tc_id_naming_prompt.py TC_ID_RULE_BODY.
_TC_ID_RULE_BODY = '''
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
  4. NEVER use TC_LOGIN unless the URL contains \'login\', \'signin\', or \'auth\'
     AND the page_title contains \'Sign In\' or \'Login\'.
  5. All test cases in one generation share the same prefix.
'''
_TC_ID_BLOCK = f'\n{TC_RULE_START}\n{_TC_ID_RULE_BODY}\n{TC_RULE_END}\n'

# ---------------------------------------------------------------------------
# OUTPUT CONTRACT body
# Canonical category list: 11 values (PAP-TSCD-005 v1.1 CORR-04)
# ---------------------------------------------------------------------------
OUTPUT_CONTRACT_BODY = """\
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
"""

CONTRACT_BLOCK = f'\n{START_SENTINEL}\n{OUTPUT_CONTRACT_BODY}\n{END_SENTINEL}\n'

# ---------------------------------------------------------------------------
# Tasks targeted by this migration
# ---------------------------------------------------------------------------
TARGET_TASKS = [
    'generate_test_cases_with_inventory',
    'generate_test_cases_deep_dive',
    'generate_test_cases',
]

# Task that has the conflicting 0012 TC_ID_RULE block (CORR-01)
TASK_WITH_0012_BLOCK = 'generate_test_cases_with_inventory'


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    conn = op.get_bind()

    # CORR-01: Remove the 0012 TC_ID_RULE block from
    # generate_test_cases_with_inventory BEFORE appending the OUTPUT CONTRACT.
    # Both blocks instruct the LLM on tc_id format but with contradictory rules:
    # 0012 mandates TC_PI_001 (underscores); the OUTPUT CONTRACT mandates
    # [TC-PI-001] (bracket+hyphen). Stripping 0012's block first ensures only
    # one format instruction is present after this migration runs.
    # [\s\S]*? — CORR-02: matches any character including newlines (non-greedy).
    conn.execute(text(r"""
        UPDATE prompt_templates
        SET system_prompt = REGEXP_REPLACE(
            system_prompt,
            '\n---TC_ID_RULE_START---[\s\S]*?---TC_ID_RULE_END---\n',
            '', 'g'
        )
        WHERE task          = :task
        AND   caller_module = 'playwright_runner'
    """), {'task': TASK_WITH_0012_BLOCK})

    # Append the OUTPUT CONTRACT to all three target tasks.
    # generate_test_cases_deep_dive may not exist yet — skip with warning;
    # migration 0016 will complete the job once that row is inserted.
    for task in TARGET_TASKS:
        result = conn.execute(text("""
            SELECT id FROM prompt_templates
            WHERE task          = :task
            AND   caller_module = 'playwright_runner'
        """), {'task': task})
        row = result.fetchone()
        if row is None:
            warnings.warn(
                f"0015 upgrade: no prompt row found for task={task!r} — "
                f"skipping. Run migration 0016 after the row is inserted."
            )
            continue
        conn.execute(text("""
            UPDATE prompt_templates
            SET system_prompt = system_prompt || :block
            WHERE task          = :task
            AND   caller_module = 'playwright_runner'
        """), {'block': CONTRACT_BLOCK, 'task': task})


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:
    conn = op.get_bind()

    # Remove the OUTPUT CONTRACT block from all three tasks.
    # CORR-02: r-string prefix required so Python does not interpret \n and \s
    # before PostgreSQL receives the query. [\s\S]*? matches any character
    # including newlines (non-greedy). The v1.0 spec had a corrupted character
    # class (backslashes stripped by Word) that silently failed to remove the block.
    for task in TARGET_TASKS:
        conn.execute(text(r"""
            UPDATE prompt_templates
            SET system_prompt = REGEXP_REPLACE(
                system_prompt,
                '\n---OUTPUT_CONTRACT_START---[\s\S]*?---OUTPUT_CONTRACT_END---\n',
                '', 'g'
            )
            WHERE task          = :task
            AND   caller_module = 'playwright_runner'
        """), {'task': task})

    # CORR-01 downgrade: restore the 0012 TC_ID_RULE block to
    # generate_test_cases_with_inventory if it is no longer present.
    result = conn.execute(text("""
        SELECT system_prompt FROM prompt_templates
        WHERE task          = :task
        AND   caller_module = 'playwright_runner'
    """), {'task': TASK_WITH_0012_BLOCK})
    row = result.fetchone()
    if row is not None and TC_RULE_START not in row[0]:
        conn.execute(text("""
            UPDATE prompt_templates
            SET system_prompt = system_prompt || :block
            WHERE task          = :task
            AND   caller_module = 'playwright_runner'
        """), {'block': _TC_ID_BLOCK, 'task': TASK_WITH_0012_BLOCK})
