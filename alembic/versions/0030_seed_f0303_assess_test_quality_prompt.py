"""F-03-03 / PAP-ASP-REQ-ASP-03 v3.0 — assess_test_quality prompt seed.

Revision ID: 0030
Revises: 0029
Create Date: 2026-04-21

Prompt-only migration. One INSERT. Pattern mirrors migrations 025,
0027, 0028 (wildcard catch-all prompt seed). No DDL changes.

Scope: seeds `assess_test_quality` v1 prompt row under the
`generation` service at `caller_module='*'`, `maturity_level='*'`,
version=1, ab_variant=NULL, is_active=TRUE. The wildcard seed
matches the post-ASP-OUT-051 pattern — every caller × maturity
combination resolves to this row via the registry fallback chain.

Prompt content verbatim from ASP-OUT-066 Task 2 directive (4 STRICT
RULES + output schema). User prompt template governs the nine
placeholders consumed by the assess_test_quality message-build
branch in app/services/generation.py::handle() (Commit A, 7ff2042).

G-PROMPT-REACH: mandatory 6-probe matrix per the expanded
ENGINEERING-PLAYBOOK §G-PROMPT-REACH rule
(playwright_runner / test_generator / '*' × L2 / '*' = 6 probes).

Downgrade: DELETE the inserted row by exact tuple.
"""
from alembic import op
import sqlalchemy as sa


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


SYSTEM_PROMPT = """\
You are a test quality assessor. Given a test asset, evaluate its
quality across five dimensions.

STRICT RULES:
1. All scores are 0.0 to 1.0.
2. overall_quality_score is the weighted mean of the four
   dimension scores.
3. suggestions are actionable improvements (2-5 items).
4. Return ONLY valid JSON.

Output schema:
{
  "step_count_adequacy":       float,
  "precondition_completeness": float,
  "assertion_coverage":        float,
  "edge_case_presence":        float,
  "overall_quality_score":     float,
  "suggestions":               [str]
}
"""


USER_PROMPT_TEMPLATE = """\
Screen: {screen_key} / Module: {module_key}
Category: {category} | Priority: {priority}

Title: {title}
Objective: {objective}

Steps:
{steps}

Preconditions (may be empty):
{preconditions}

Expected result:
{expected_result}

Assess the quality of this test asset per the output schema.
"""


def upgrade():
    op.execute(
        sa.text("""
            INSERT INTO prompt_templates
              (service_type, task, caller_module, maturity_level, version,
               is_active, ab_variant, system_prompt, user_prompt_template)
            VALUES
              ('generation', 'assess_test_quality',
               '*', '*', 1, TRUE, NULL,
               :sys, :usr)
        """).bindparams(
            sys=SYSTEM_PROMPT,
            usr=USER_PROMPT_TEMPLATE,
        )
    )


def downgrade():
    op.execute("""
        DELETE FROM prompt_templates
        WHERE service_type = 'generation'
          AND task = 'assess_test_quality'
          AND caller_module = '*'
          AND maturity_level = '*'
          AND version = 1;
    """)
