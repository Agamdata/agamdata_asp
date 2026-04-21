"""F-03-02 / ASP-OUT-051 — wildcard catch-all prompt rows for four F-03-02 tasks.

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-21

P1 FIX for PAP Block 3 500 errors (ASP-OUT-045 → ASP-OUT-051 ruling
Option A). Migrations 026 / 027 seeded F-03-02 prompt rows only at
`caller_module='test_generator'`; any PAP invocation using any other
caller_module (including the canonical `playwright_runner`) failed all
four levels of the registry fallback chain and raised
PromptNotFoundError, surfacing as 500 at the handler boundary.

This migration inserts **four** additional prompt rows — one per task —
at `caller_module='*'`, `maturity_level='*'`. The content of each row
is copied verbatim at migration-runtime from the existing
test_generator row via `INSERT ... SELECT`, eliminating any risk of
paste-time drift.

No deactivations. The test_generator rows remain active for future
caller-specific tuning.

Reachability after this migration:
  (playwright_runner, L2)     → matches (*, *) at fallback level 4
  (playwright_runner, *)      → matches (*, *)
  (test_generator, L2)        → matches (test_generator, *) at level 2
  (test_generator, *)         → matches exactly
  (<any_other>, <any_mat>)    → matches (*, *) at level 4

Precedent: same resolution pattern as ASP-OUT-014 fix (migration 024
regression — 4-level fallback chain in get_prompt_variant).

ENGINEERING-PLAYBOOK §G-PROMPT-REACH updated in the same commit to
mandate reach probing against multiple caller_module values (not just
the seeded one).

Downgrade: DELETE the four wildcard rows by exact tuple.
"""
from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


# One INSERT...SELECT per task for audit clarity (four ops; Op 5 is
# "no deactivation" per directive — intentionally not an SQL statement).
_TASKS = [
    ("generation", "draft_steps"),
    ("generation", "suggest_preconditions"),
    ("generation", "propose_edge_cases"),
    ("nlp",        "extract_test_entities"),
]


_INSERT_WILDCARD = """
    INSERT INTO prompt_templates
      (service_type, task, caller_module, maturity_level, version,
       is_active, ab_variant, system_prompt, user_prompt_template)
    SELECT
      service_type,            -- preserve service_type from source row
      task,                    -- preserve task from source row
      '*',                     -- WILDCARD caller (this migration's purpose)
      '*',                     -- WILDCARD maturity
      1,                       -- version 1 (first wildcard seed)
      TRUE,                    -- active
      NULL,                    -- no ab_variant
      system_prompt,           -- COPY VERBATIM from test_generator row
      user_prompt_template     -- COPY VERBATIM from test_generator row
    FROM prompt_templates
    WHERE service_type = :service_type
      AND task          = :task
      AND caller_module = 'test_generator'
      AND maturity_level = '*'
      AND version       = 1
      AND is_active     = TRUE
"""


def upgrade():
    conn = op.get_bind()
    for service_type, task in _TASKS:
        # Safety probe: fail loudly if the source row is missing
        # (migration 026/027 prerequisite not applied).
        count = conn.execute(
            sa.text("""
                SELECT COUNT(*) FROM prompt_templates
                WHERE service_type = :s AND task = :t
                  AND caller_module = 'test_generator'
                  AND maturity_level = '*' AND version = 1
                  AND is_active = TRUE
            """),
            {"s": service_type, "t": task},
        ).scalar()
        if count != 1:
            raise RuntimeError(
                f"Migration 0028 prerequisite missing: expected exactly 1 "
                f"test_generator source row for ({service_type}, {task}); "
                f"found {count}. Migrations 0026/0027 must be applied first."
            )

        # Idempotency guard: don't duplicate if a wildcard row already
        # exists (e.g. from a previous partial apply).
        already = conn.execute(
            sa.text("""
                SELECT COUNT(*) FROM prompt_templates
                WHERE service_type = :s AND task = :t
                  AND caller_module = '*' AND maturity_level = '*'
                  AND version = 1
            """),
            {"s": service_type, "t": task},
        ).scalar()
        if already > 0:
            continue

        op.execute(
            sa.text(_INSERT_WILDCARD).bindparams(
                service_type=service_type, task=task,
            )
        )


def downgrade():
    op.execute("""
        DELETE FROM prompt_templates
        WHERE caller_module = '*'
          AND maturity_level = '*'
          AND version = 1
          AND (
            (service_type = 'generation' AND task IN (
                'draft_steps','suggest_preconditions','propose_edge_cases'
             ))
            OR
            (service_type = 'nlp' AND task = 'extract_test_entities')
          );
    """)
