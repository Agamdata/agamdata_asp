"""F-03-02 / PAP-ASP-REQ-ASP-02 v1.0 — NLP extract_test_entities prompt row.

Revision ID: 0027
Revises: 0026
Create Date: 2026-04-21

Prompt-only migration. One INSERT. Pattern mirrors migrations 025
and 026. No DDL changes.

Scope: seeds `extract_test_entities` v1 prompt row under the `nlp`
service, `caller_module="test_generator"` (PAP's test-generator panel
is the caller for F-03-02). `maturity_level="*"`. No `ab_variant`
(NULL) — single mode per task.

Service-naming note (ASP-OUT-034 flag acknowledged by ASP-OUT-036):
The Architect directive labels this as "ASP-02 (nlp)". ASP-02 in the
repo service registry is the RAG service (governed under
ASP-FEAT-ASP-02 v1.0). The task lives on the NLP service — the
prompt_templates row uses `service_type='nlp'` and the handler is
in `app/services/nlp.py`. The ASP-02 label in the directive header
is an informal grouping of the four F-03-02 tasks; the build
correctly targets NLP.

Prompt content locked at ASP-OUT-036 directive (Principal Architect,
2026-04-21). System-prompt wording is verbatim; user_prompt_template
is the minimal rendering contract for the handler.

G-PROMPT-REACH: caller_module='test_generator' + maturity_level='*'
is reachable for every maturity input from the test_generator caller
via level 2 of the 4-level fallback chain.

Downgrade: DELETE the inserted row by its exact tuple.
"""
from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


SYSTEM_PROMPT = """\
You are a test entity extractor. Given freeform text describing a
test scenario or requirements, extract structured test-relevant
entities.

STRICT RULES:
1. Extract only entities explicitly mentioned or strongly implied in
   the text. Do not invent entities.
2. Each list may be empty if no relevant entities are present.
3. Return ONLY valid JSON. No markdown.

Output schema:
{"entities": {
  "required_fields": ["str"],
  "actions": ["str"],
  "validation_cases": ["str"],
  "success_outcomes": ["str"]},
"confidence": 0.0-1.0}
"""


USER_PROMPT_TEMPLATE = """\
Context — Screen: {screen_key} / Module: {module_key} / Category: {category}

Text to analyse:
{text}

Extract structured test entities from the text above. Return JSON per
the output schema. If the text contains no entities for a given
bucket, return that bucket as an empty list.
"""


def upgrade():
    op.execute(
        sa.text("""
            INSERT INTO prompt_templates
              (service_type, task, caller_module, maturity_level, version,
               is_active, ab_variant, system_prompt, user_prompt_template)
            VALUES
              ('nlp', 'extract_test_entities',
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
          AND task = 'extract_test_entities'
          AND caller_module = 'test_generator'
          AND maturity_level = '*'
          AND version = 1;
    """)
