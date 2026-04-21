"""ASP-FEAT-ASP-04 v1.0 — documents table + extract_invoice prompt seed.

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-21

First DDL migration since 0023. Adds the `documents` registry table
governed in ASP-FEAT-ASP-04 v1.0 §5.1 — 11 columns, 1 CHECK
constraint, 2 foreign keys, 2 indexes (one partial).

Also seeds the `extract_invoice` prompt row governed in §9.3 / §9.5.
Single migration (DDL + prompt seed bundled) because the prompt is
a net-new task registration and the table is a new consumer surface
for the extracted field set — they ship together for the demo flow.

Governance:
- Spec: ASP-FEAT-ASP-04 v1.0 (draft; Batches 1-3 surfaced for review;
  Batch 3 accepted per ASP-OUT-055)
- Implementation item: I-DOC-03 (per §11 checklist)
- Pre-write gate: G-PROMPT-REACH 6-probe matrix for extract_invoice
  (playwright_runner / test_generator / '*' × L2 / '*') — mandatory
  per ENGINEERING-PLAYBOOK.md §G-PROMPT-REACH expanded rule
- Fresh-DB round-trip: ADR-029 mandatory

Downgrade: drop the two indexes, drop the documents table, delete
the extract_invoice prompt row by exact tuple.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


# --- extract_invoice prompt body (ASP-FEAT-ASP-04 v1.0 §9.3) --------------

EXTRACT_INVOICE_SYSTEM = """\
You are an invoice extraction specialist. Given an invoice PDF (OCR
text supplied in user message), extract structured fields.

STRICT RULES:
1. Extract ONLY fields visible in the document. If a field is not
   present, return null. Never invent values.
2. line_items: one entry per line on the invoice. Omit line_items
   that are not billable (section headers, totals, blank lines).
3. currency: ISO 4217 three-letter code (USD, EUR, GBP, ...) when
   determinable. null if ambiguous.
4. subtotal / tax_amount / total_amount: numeric values only; strip
   currency symbols and thousands separators.
5. invoice_date / due_date: exact string as shown on the invoice.
   Do NOT normalise the format. Downstream consumers normalise.
6. Return ONLY valid JSON. No markdown. No preamble.

Output schema:
{
  "vendor": str | null,
  "invoice_number": str | null,
  "invoice_date": str | null,
  "due_date": str | null,
  "line_items": [
    {"description": str, "quantity": float | null,
     "unit_price": float | null, "amount": float | null}
  ],
  "subtotal": float | null,
  "tax_amount": float | null,
  "total_amount": float | null,
  "currency": str | null,
  "payment_terms": str | null
}
"""

EXTRACT_INVOICE_USER_TEMPLATE = """\
{document_text}
"""


def upgrade():
    # --- documents table DDL --------------------------------------------

    op.create_table(
        "documents",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=True),
        sa.Column("classification_confidence", sa.Float, nullable=True),
        sa.Column(
            "extraction_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("extraction_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("extracted_fields", JSONB, nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            ondelete="CASCADE",
            name="fk_documents_tenant",
        ),
        sa.ForeignKeyConstraint(
            # FK targets async_jobs.id (UUID PK), not the VARCHAR
            # job_id column. Consumer-facing job_id is resolved via a
            # join when ops-side queries need the public-facing job
            # identifier; internal integrity uses the UUID PK.
            ["extraction_job_id"],
            ["async_jobs.id"],
            ondelete="SET NULL",
            name="fk_documents_extraction_job",
        ),
        sa.CheckConstraint(
            "extraction_status IN ('pending','classifying','extracting',"
            "'complete','failed')",
            name="ck_documents_extraction_status",
        ),
    )

    op.create_index(
        "ix_documents_tenant_uploaded",
        "documents",
        ["tenant_id", sa.text("uploaded_at DESC")],
    )

    op.create_index(
        "ix_documents_extraction_status",
        "documents",
        ["extraction_status"],
        postgresql_where=sa.text(
            "extraction_status IN ('classifying','extracting')"
        ),
    )

    # --- extract_invoice prompt seed (service_type='doc_intelligence') ----

    op.execute(
        sa.text(
            """
            INSERT INTO prompt_templates
              (service_type, task, caller_module, maturity_level, version,
               is_active, ab_variant, system_prompt, user_prompt_template)
            VALUES
              ('doc_intelligence', 'extract_invoice',
               '*', '*', 1, TRUE, NULL,
               :sys, :usr)
            """
        ).bindparams(
            sys=EXTRACT_INVOICE_SYSTEM,
            usr=EXTRACT_INVOICE_USER_TEMPLATE,
        )
    )


def downgrade():
    # Prompt row first (simpler rollback order)
    op.execute(
        """
        DELETE FROM prompt_templates
        WHERE service_type = 'doc_intelligence'
          AND task = 'extract_invoice'
          AND caller_module = '*'
          AND maturity_level = '*'
          AND version = 1;
        """
    )

    # Indexes then table
    op.drop_index("ix_documents_extraction_status", table_name="documents")
    op.drop_index("ix_documents_tenant_uploaded", table_name="documents")
    op.drop_table("documents")
