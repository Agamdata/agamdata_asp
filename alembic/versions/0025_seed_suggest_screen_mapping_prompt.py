"""PAP-ASP-REQ-ASP-01 v2.0 — suggest_screen_mapping prompt row.

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-18

Prompt-only migration. One INSERT. Pattern mirrors migration 022 and
other single-prompt-seed migrations. No DDL changes.

Scope: seeds `suggest_screen_mapping` v1 prompt row under the `nlp`
service, `caller_module="test_generator"` (PAP's F-01-10 interactive
test-generator panel is the primary caller; the task is tied to the
same PAP feature family that owns F-01-10). `maturity_level="*"`.
No `ab_variant` (NULL) — single mode per task.

Prompt content locked at ASP-OUT-020 directive (Principal Architect,
2026-04-18).

Downgrade: DELETE the inserted row by its exact tuple.
"""
from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


SYSTEM_PROMPT = """\
You are an expert CRM assistant that maps web pages to their matching
internal modules. You receive page metadata and a list of available
modules; you return the best matching module_key from that list.

STRICT RULES:
1. Return ONLY module_key values present in the available_modules input
   list. Never invent, suggest, or paraphrase a module_key that is not
   in the provided list. If no module fits, return null.
2. Return ONLY valid JSON. No markdown fences. No preamble. No
   explanation outside the JSON.

Output JSON schema — follow exactly:
{
  "suggested_module_key": "string from available_modules or null",
  "suggested_screen_name": "string describing the screen (e.g. 'Lead List', 'Customer Detail') or null",
  "confidence": 0.0 to 1.0
}

Set confidence based on match strength:
  0.9-1.0  → unambiguous match (URL, title, and type all align)
  0.7-0.89 → strong match (URL or title clearly indicates the module)
  0.4-0.69 → plausible match but with ambiguity
  0.0-0.39 → weak or no match → return suggested_module_key=null,
             suggested_screen_name=null, confidence=0.0
"""


USER_PROMPT_TEMPLATE = """\
Page URL: {page_url}
Page title: {page_title}
Page type: {page_type}

Available modules:
{available_modules}

Select the best matching module for this page. Return null if
confidence is low.
"""


def upgrade():
    op.execute(
        sa.text("""
            INSERT INTO prompt_templates
              (service_type, task, caller_module, maturity_level, version,
               is_active, ab_variant, system_prompt, user_prompt_template)
            VALUES
              ('nlp', 'suggest_screen_mapping',
               'test_generator', '*', 1, TRUE, NULL,
               :sys, :usr)
        """).bindparams(
            sys=SYSTEM_PROMPT,
            usr=USER_PROMPT_TEMPLATE,
        )
    )


def downgrade():
    op.execute("""
        DELETE FROM prompt_templates
        WHERE service_type = 'nlp'
          AND task = 'suggest_screen_mapping'
          AND caller_module = 'test_generator'
          AND maturity_level = '*'
          AND version = 1;
    """)
