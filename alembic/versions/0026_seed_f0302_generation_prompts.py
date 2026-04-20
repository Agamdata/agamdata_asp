"""F-03-02 / PAP-ASP-REQ-ASP-02 v1.0 — three ASP-03 prompt rows.

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-21

Prompt-only migration. Three INSERTs. Pattern mirrors migration 025
(suggest_screen_mapping). No DDL changes.

Scope: seeds `draft_steps`, `suggest_preconditions`, `propose_edge_cases`
v1 prompt rows under the `generation` service, `caller_module="test_generator"`
(PAP's test-generator panel is the caller for F-03-02 per ASP-OUT-036).
`maturity_level="*"`. No `ab_variant` (NULL) — single mode per task.

Prompt content locked at ASP-OUT-036 directive (Principal Architect,
2026-04-21). System-prompt wording is verbatim from the directive;
user_prompt_template is the minimal rendering contract for the handler
(see app/services/generation.py F-03-02 additions in Commit D).

G-PROMPT-REACH check: the handlers dispatch get_prompt with
caller_module=req.caller_module, maturity_level=req.user_context.maturity_level.
The registry's 4-level fallback chain resolves
(test_generator, L0/L1/L2/L3) → (test_generator, *) via level 2 of the chain.
Rows at caller_module="test_generator", maturity_level="*" are reachable
for every maturity input from the test_generator caller. No (*, *) catch-all
needed; PAP test-generator is the only governed caller for these tasks.

Downgrade: DELETE the three inserted rows by their exact tuples.
"""
from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


# --- draft_steps -----------------------------------------------------------

DRAFT_STEPS_SYSTEM = """\
You are a Playwright test step generator. Given a test asset context,
generate the next logical test steps.

STRICT RULES:
1. Continue from the highest existing step_no. Never duplicate step
   numbers.
2. Generate 3-7 steps unless context clearly requires fewer.
3. selector is always null — PAP resolves locators separately.
4. Return ONLY valid JSON. No markdown.

Output schema:
{"result": [{"step_no": int, "action": str, "selector": null,
"expected": str}], "confidence": 0.0-1.0}
"""

DRAFT_STEPS_USER = """\
Screen: {screen_key} / Module: {module_key}
Category: {category} | Priority: {priority}

Title: {title}
Objective: {objective}

Existing steps (may be empty):
{existing_steps}

Preconditions (may be empty):
{preconditions}

Produce the next test steps as JSON per the output schema.
"""


# --- suggest_preconditions -------------------------------------------------

SUGGEST_PRECONDITIONS_SYSTEM = """\
You are a test precondition advisor. Given a test asset context,
suggest the prerequisite conditions an engineer should verify before
running this test.

STRICT RULES:
1. Return 2-5 preconditions.
2. Each is a single actionable string.
3. Do not duplicate existing preconditions provided in context.
4. Return ONLY valid JSON. No markdown.

Output schema:
{"result": ["string"], "confidence": 0.0-1.0}
"""

SUGGEST_PRECONDITIONS_USER = """\
Screen: {screen_key} / Module: {module_key}
Category: {category} | Priority: {priority}

Title: {title}
Objective: {objective}

Existing preconditions (do not duplicate — may be empty):
{preconditions}

Existing steps (may be empty):
{existing_steps}

Return the suggested preconditions as JSON per the output schema.
"""


# --- propose_edge_cases ----------------------------------------------------

PROPOSE_EDGE_CASES_SYSTEM = """\
You are a test edge case advisor. Given a test asset context, propose
edge cases the engineer has not yet covered.

STRICT RULES:
1. Propose 3-5 edge cases.
2. Each has a title and objective.
3. Focus on boundary conditions, error paths, and permission variations
   relevant to the category.
4. Return ONLY valid JSON. No markdown.

Output schema:
{"result": [{"title": str, "objective": str}], "confidence": 0.0-1.0}
"""

PROPOSE_EDGE_CASES_USER = """\
Screen: {screen_key} / Module: {module_key}
Category: {category} | Priority: {priority}

Title: {title}
Objective: {objective}

Existing steps (may be empty):
{existing_steps}

Existing preconditions (may be empty):
{preconditions}

Return edge cases as JSON per the output schema. Focus on uncovered
boundary conditions, error paths, and permission variations relevant
to the {category} category.
"""


_INSERT_SQL = """
    INSERT INTO prompt_templates
      (service_type, task, caller_module, maturity_level, version,
       is_active, ab_variant, system_prompt, user_prompt_template)
    VALUES
      ('generation', :task, 'test_generator', '*', 1, TRUE, NULL,
       :sys, :usr)
"""


def upgrade():
    for task, sys_prompt, usr_prompt in (
        ("draft_steps",            DRAFT_STEPS_SYSTEM,           DRAFT_STEPS_USER),
        ("suggest_preconditions",  SUGGEST_PRECONDITIONS_SYSTEM, SUGGEST_PRECONDITIONS_USER),
        ("propose_edge_cases",     PROPOSE_EDGE_CASES_SYSTEM,    PROPOSE_EDGE_CASES_USER),
    ):
        op.execute(
            sa.text(_INSERT_SQL).bindparams(
                task=task, sys=sys_prompt, usr=usr_prompt
            )
        )


def downgrade():
    op.execute("""
        DELETE FROM prompt_templates
        WHERE service_type = 'generation'
          AND task IN ('draft_steps', 'suggest_preconditions', 'propose_edge_cases')
          AND caller_module = 'test_generator'
          AND maturity_level = '*'
          AND version = 1;
    """)
