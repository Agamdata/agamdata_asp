"""seed classify_probe_result prompt template for ASP-01 NLP

Revision ID: 0017 (was 0006 — renumbered per ASP-NOTE-004 chain reconciliation)
Revises: 0016
Create Date: 2026-04-10 00:00:00.000000

Spec: ASP-FEAT-ASP-01 v1.2, Section 9.2
Prompt source: PAP-ASP-REQ-ASP-01 v1.0 Section 5 (canonical)
"""
from alembic import op
from sqlalchemy import text

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

# PAP-ASP-REQ-ASP-01 canonical system prompt
SYSTEM_PROMPT = """\
You are a web form behavior classifier for automated test generation.
You receive observations from Playwright form submission tests and classify
the outcome so that test assertions can be generated accurately.

Classify the outcome as EXACTLY one of:
- success: form accepted and user moved forward (redirect to new page, or
  success message visible)
- validation_error: server rejected the data (same page stays, error messages
  visible on fields or globally)
- auth_redirect: submission redirected to login/auth page (session expired or
  user unauthorised)
- server_error: HTTP 5xx response or application error/crash page
- unknown: cannot determine reliably (CAPTCHA detected, no observable change,
  JS-only SPA, timeout)

Return ONLY valid JSON. No preamble. No markdown fences. Schema:
{
  "outcome": "success|validation_error|auth_redirect|server_error|unknown",
  "confidence": 0.0-1.0,
  "error_messages": ["list of extracted error strings"],
  "success_indicators": ["list of extracted success strings"],
  "redirect_target": "url or null",
  "reasoning": "one sentence explanation"
}"""

# PAP-ASP-REQ-ASP-01 canonical user prompt template
# [v1.1] F-2: includes {page_type} variable
USER_TEMPLATE = """\
Form URL: {page_url}
Page type: {page_type}
Fields submitted: {submitted_fields}
Post-submit URL: {post_submit_url}
Post-submit HTTP status: {post_submit_status}
Visible page text after submission (max 2000 chars):
{visible_text}

Classify the form submission outcome."""


def upgrade():
    conn = op.get_bind()
    conn.execute(text("""
        INSERT INTO prompt_templates
          (service_type, task, caller_module, maturity_level,
           system_prompt, user_prompt_template, is_active)
        VALUES
          (:svc, :task, :mod, :mat, :sys, :usr, true)
        ON CONFLICT (service_type, task, caller_module, maturity_level,
                     version, ab_variant)
        DO NOTHING
    """), {
        "svc":  "nlp",
        "task": "classify_probe_result",
        "mod":  "playwright_runner",
        "mat":  "*",
        "sys":  SYSTEM_PROMPT,
        "usr":  USER_TEMPLATE,
    })


def downgrade():
    conn = op.get_bind()
    conn.execute(text("""
        DELETE FROM prompt_templates
        WHERE service_type = 'nlp'
          AND task = 'classify_probe_result'
          AND caller_module = 'playwright_runner'
    """))
