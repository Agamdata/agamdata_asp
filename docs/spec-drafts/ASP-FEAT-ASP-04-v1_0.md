# ASP-FEAT-ASP-04 v1.0 — Doc Intelligence + Dashboard Panel (joint)

| Field | Value |
|---|---|
| Feature ID | ASP-FEAT-ASP-04 |
| Version | v1.0-draft |
| Services governed | ASP-04 Doc Intelligence · ASP-13 Dashboard Intelligence (Doc Intelligence panel) |
| Status | **IN SPEC — BATCH 1 SURFACED FOR REVIEW** |
| Authored | 2026-04-21 |
| Commit head | `6f5711c` (post-DEFECT-024 filing) |
| Migration head | **0027** → 0028 (DDL: documents table) → 0029 (prompt seed: extract_invoice) |
| Spec driver | Product demo — invoice upload / classify / extract / review panel |
| Governance trail | ASP-OUT-041 (pre-spec survey) · ASP-OUT-042 (survey accepted, 6 rulings, Batch 1 green light) |
| Predecessor | None — ASP-04 was ACTIVE (pre-governance). This is the first full governance spec for the service. |

---

## §1 Summary

ASP-04 Doc Intelligence and ASP-13 Dashboard Intelligence (Doc Intelligence
panel) are governed together in this v1.0 cycle. The product demo drives
the scope: an engineer uploads an invoice PDF, the backend classifies it,
extracts structured fields, and a dashboard panel renders the original
PDF alongside the extracted fields with confidence indicators.

**Three ASP-04 tasks are in scope:**

- `classify_document` — **existing**, governed in this cycle (no
  implementation change; documented for consumer contract lock).
- `extract_document` — **existing**, governed in this cycle (no
  implementation change; documented for consumer contract lock).
- `extract_invoice` — **NEW** implementation, invoice-tuned prompt,
  invoice-specific output schema.

**ASP-13 surface** gains the Doc Intelligence dashboard panel: a
server-rendered Jinja2 + HTMX page that consumes the existing async
job-polling contract (`GET /api/v1/ai/jobs/{job_id}`), renders PDFs
inline via `pdf.js`, and shows extracted fields in a structured
two-panel layout.

**Target demo flow (spec governs this exact sequence):**

1. Engineer uploads invoice PDF via the dashboard panel.
2. Frontend POSTs multipart to the new `POST /api/v1/ai/documents`
   endpoint → returns `{document_id, storage_path, ...}`.
3. Frontend invokes `classify_document` via the Gateway with the
   returned `file_key`; polls the job until complete. Dashboard shows
   `"Invoice — 94% confidence"` badge.
4. Frontend invokes `extract_invoice` with the same `file_key`;
   polls the job until complete. Dashboard renders the original PDF
   on the left panel and the structured extracted fields on the right
   panel with per-field confidence indicators.

**Audiences.** Internal (ops + product review) and external prospects
(sales demos). LogiCRM onboarding has a hard dependency on this demo
closing.

**Quality tier.** `enhanced` (Claude Sonnet) for both `classify_document`
and `extract_invoice` — extraction precision on messy real invoices
warrants the enhanced tier. `extract_document` retains `standard` per
its existing contract.

**Async pattern.** Celery (`asp.doc_intelligence` Celery task, same
name as the existing worker registration). The task name is unchanged;
only the dispatch branches internally on `req.task` as it already does.

**Governing driver — DEFECT-024.** Per ASP-OUT-042, the psycopg2 class
of bug surfaced in the pre-spec survey (G-04-06) is scheduled as
Stream A / S-1 and **must ship before** any other implementation in
this cycle. Without that fix, the Celery worker cannot write to
Postgres — every ASP-04 task would fail on first DB transition.

---

## §2 Background

### §2.1 Pre-governance state

ASP-04 was ACTIVE (pre-governance) from pilot launch through
2026-04-21. It was present in `app/services/doc_intelligence.py` (267
LOC) and wired into the Gateway router as an async service; its two
tasks were reachable via prompt rows seeded in migration `0002`.

No consumer has invoked the ASP-04 Celery worker end-to-end in the
pilot environment. The enqueue path succeeded (the `async_jobs` row
was created via the async session); the worker path has never
completed a single run because of **DEFECT-024** — the sync `psycopg2`
class of bug identical to the ASP-10 cost aggregator defect
(DEFECT-022, resolved 2026-04-18).

ASP-13 Dashboard Intelligence was ACTIVE (pre-governance) with four
tasks (`interpret_chart`, `narrate_dashboard`, `detect_anomaly`,
`suggest_drilldown`) but **no frontend**. Every call was consumed via
the Gateway by upstream services (LogiCRM, PAP). The product-demo
dashboard panel is the first frontend asset in this repo.

### §2.2 Driving defects, gaps, and decisions (from pre-spec survey)

The ASP-OUT-041 pre-spec survey (DEV-IN-041,
`docs/spec-drafts/ASP-FEAT-ASP-04-v1_0-PRE-SPEC-SURVEY.md`) surfaced
11 gaps. Rulings landed in ASP-OUT-042 are summarised below; the
complete analysis remains the governed input.

| ID | Severity | Disposition in v1.0 |
|---|---|---|
| **G-04-01** no upload endpoint | HIGH | S-3 — `POST /api/v1/ai/documents` multipart (Q-2 Option A) |
| **G-04-02** tasks absent from TASK_SCHEMA_MODELS | MEDIUM | S-5 — register all three doc tasks (ADR-030) |
| **G-04-03** `ExtractDocumentOutput.fields` untyped | MEDIUM | S-4 — `ExtractInvoiceOutput` governed (Q-6) |
| **G-04-04** cost emission not wrapped (ADR-006 gap) | MEDIUM | S-6 — try/except in doc handler |
| **G-04-05** no structlog transitions in Celery worker | LOW | S-7 — three events (running/completed/failed) |
| **G-04-06** **psycopg2 class-of-bug (DEFECT-022 class)** | **CRITICAL** | **S-1** — asyncpg port per DEFECT-022 playbook (Q-4 Option A); ships FIRST; **ASP-DEFECT-024** filed |
| **G-04-07** no invoice-specific prompt row | MEDIUM | Migration 0029 — seed `extract_invoice` prompt |
| **G-13-01** no frontend at all | HIGH | S-8 — Jinja2 + HTMX + pdf.js, server-rendered (Q-5 Option D) |
| **G-13-02** no file-upload UI | HIGH | S-8 — multipart form + HTMX swap |
| **G-13-03** no PDF viewer | HIGH | S-8 — pdf.js CDN + `<canvas>` pipeline |
| **G-13-04** no structured-field review panel | HIGH | S-8 — Jinja partial with confidence-badge component |

### §2.3 Cross-references

- `docs/spec-drafts/ASP-FEAT-ASP-04-v1_0-PRE-SPEC-SURVEY.md` —
  accepted survey (commit `cf09432`).
- `ASP-DEFECT-REGISTER.md` — **ASP-DEFECT-024** filed (commit
  `6f5711c`); DEFECT-022 closure (commit `d158221`) for precedent.
- `ENGINEERING-PLAYBOOK.md` §12 — asyncpg loop-affinity rule (source
  of truth for the S-1 remediation pattern).
- `app/cost/aggregator.py` — governed reference implementation of the
  per-invocation `create_async_engine()` + `engine.dispose()` pattern.

---

## §3 Scope

### §3.1 In scope

Eight governance items (S-1..S-8), sequenced per ASP-OUT-042:

| ID | Item | Stream | Sequencing note |
|---|---|---|---|
| **S-1** | DEFECT-024 fix — asyncpg port at all three sync sites in `doc_intelligence.py` | A | **FIRST** — gates the rest of the cycle; 9-successive-invocation verification (same contract as DEFECT-022) |
| **S-2** | `documents` registry table (migration 0028, DDL) | A | Per Q-3 INCLUDE ruling — overrules the survey's "defer to v1.1" recommendation |
| **S-3** | `POST /api/v1/ai/documents` multipart upload endpoint | A | Depends on S-2 (writes `documents` row); auth via `X-ASP-API-Key`; tenant-scoped storage path |
| **S-4** | `extract_invoice` task + `ExtractInvoiceOutput` + `LineItem` Pydantic models | A | New `app/schemas/doc_intelligence_schemas.py`; existing `ExtractDocumentOutput`/`ClassifyDocumentOutput` migrated into the same file |
| **S-5** | ADR-030 schema registration for all three doc tasks | A | `TASK_SCHEMA_MODELS` entries in `app/api/capabilities.py` |
| **S-6** | ADR-006 fix — `try/except` around cost emission in Celery worker | A | Bundled with S-1 (same file touch) |
| **S-7** | structlog transitions for Celery doc task — `running` / `completed` / `failed` | A | ADR-010 coverage (`asp_doc_job_running`, `asp_doc_job_completed`, `asp_doc_job_failed`) |
| **S-8** | ASP-13 Doc Intelligence dashboard panel — Jinja2 + HTMX + pdf.js | B | Server-rendered; no build tooling; loads HTMX + pdf.js via CDN |

Migrations:

| # | Type | Scope |
|---|---|---|
| **0028** | DDL | `documents` table (11 columns, 1 CHECK, 2 indexes, 2 FKs) — see §5 |
| **0029** | Prompt-only | Seed `extract_invoice` prompt row on `doc_intelligence` service |

### §3.2 Out of scope (v1.0)

Explicitly excluded per ASP-OUT-042 directive:

- `documents` audit history / versioning (no version-of-extraction rows).
- Multi-page PDF splitting (single upload per document).
- Non-invoice document extraction UI (generic extractor has no panel
  in v1.0 — only the invoice flow renders).
- LogiCRM direct DB integration (demo stands alone).
- Mobile-responsive layout (desktop demo target).

### §3.3 Pre-write gate (summary)

| Gate | Status |
|---|---|
| G-1 Schema | §5 authored in this batch |
| G-2 Types | §5 authored in this batch |
| G-3 Contract | **Pending §6** (Batch 2) |
| G-4 Audit (CHECK) | One CHECK on `documents.extraction_status`; §5 |
| G-5 Migration | 0028 (DDL) then 0029 (prompt); single head after apply |
| G-6 Frontend | **Pending §11 + S-8** (Batch 3) |
| G-7 Dependency | New modules: `app/schemas/doc_intelligence_schemas.py`, `app/api/documents.py` (upload endpoint), `app/ui/dashboard.py` (UI router), templates + static assets |
| G-8 Prompt Reach | **Pending migration 0029** — reach check on `(*, *)` for `extract_invoice`; consistent with prior `extract_document`/`classify_document` rows |

---

## §4 Classification

### §4.1 Service type

- **ASP-04 Doc Intelligence** — Asynchronous (Celery). Zone 2 Shared
  Contract surface via the Gateway; ADR-001 governs the zone
  boundary. No new zone classification is introduced.
- **ASP-13 Dashboard Intelligence** — Synchronous (Gateway LLM calls
  for the four existing tasks). The **new dashboard panel** (S-8) is
  a UI-layer Zone 2 surface served by the same `ai-service` container
  at `GET /dashboard/doc-intelligence` (and supporting HTMX partials).
  The LLM contract for the four existing tasks does not change.

### §4.2 LLM tier per task

| Task | Tier | Model (via ASP-11 Model Router) | Why |
|---|---|---|---|
| `classify_document` (existing) | `standard` → **`enhanced`** | Claude Haiku → **Claude Sonnet** | Directive-specified upgrade to enhanced for the demo; classification precision on real invoices exceeds Haiku's reliability. Change is additive at the request layer (`quality_tier="enhanced"`). |
| `extract_document` (existing) | `standard` | Claude Haiku | Unchanged; generic extraction; not on the demo path. |
| `extract_invoice` (NEW) | `enhanced` | Claude Sonnet | Structured-field extraction with per-field confidence demands Sonnet. |

No change to ASP-11 Model Router logic is required; `quality_tier` on
the `InvokeRequest` already selects the model.

### §4.3 Async contract

- **Request.** `POST /api/v1/ai/invoke` with
  `service_type="doc_intelligence"` and one of the three tasks. Gateway
  returns `JobAcceptedResponse(request_id, job_id, status='queued')`
  immediately.
- **Worker.** `asp.doc_intelligence` Celery task (already registered —
  no new task name). Transitions through
  `queued → running → completed | failed` on `async_jobs.status`.
- **Polling.** `GET /api/v1/ai/jobs/{job_id}` — tenant-scoped, 404 on
  cross-tenant (ADR-022 leak-safe), returns full result on
  `status='completed'`.
- **Webhook.** Optional `payload.webhook_url` fires on completion via
  `app.webhook.service.fire_webhook`.

The async contract itself is unchanged from the pre-governance state —
this spec makes the existing contract formal (consumer lock) and fixes
the psycopg2 bug that has prevented it from actually working.

### §4.4 Binary input handling

ASP-04 handles binary input (PDF / DOCX) via MinIO. File contents
**never** transit the Gateway after the initial upload (S-3):

1. Client uploads via `POST /api/v1/ai/documents` → file is written to
   `asp-documents/{tenant_id}/{document_id}.pdf` in MinIO. Response
   carries only the `document_id`, the `storage_path`, and metadata.
2. Client invokes `classify_document` / `extract_invoice` with
   `payload.file_key = storage_path`. The Gateway validates the
   `tenant_id` prefix and enqueues the Celery task.
3. The worker downloads the bytes via `app.infra.storage.download`
   inside the Celery task only. No bytes cross the Gateway boundary
   after upload.

### §4.5 Reference implementation precedents

- **DEFECT-022 resolution** (`app/cost/aggregator.py`) — governed
  pattern for per-invocation async engine in a Celery task. S-1
  follows this pattern verbatim.
- **ASP-FEAT-ASP-00 v1.0** (Gateway) — RFC 7807 error envelope, auth
  pattern, capabilities surface. S-3 upload endpoint and S-5 schema
  registration both inherit the Gateway's conventions.
- **ASP-FEAT-ASP-02 v1.0** (RAG + Ontology) — 4-level fallback in
  prompt registry (G-PROMPT-REACH gate); applies to the `extract_invoice`
  prompt reach verification (§5 / migration 0029).

---

## §5 Data Model

### §5.1 New table — `documents`

Migration `0028` (DDL) introduces a single new table. Prompt template
changes are deferred to migration `0029` (prompt-only seed for
`extract_invoice`), matching the established migration-per-concern
pattern.

**Table definition (governed):**

```sql
CREATE TABLE documents (
    id                          UUID         NOT NULL PRIMARY KEY
                                             DEFAULT gen_random_uuid(),
    tenant_id                   UUID         NOT NULL
                                             REFERENCES tenants(id)
                                             ON DELETE CASCADE,
    original_filename           VARCHAR(255) NOT NULL,
    storage_path                VARCHAR(512) NOT NULL,
    document_type               VARCHAR(64)  NULL,
    classification_confidence   FLOAT        NULL,
    extraction_status           VARCHAR(32)  NOT NULL DEFAULT 'pending',
    extraction_job_id           UUID         NULL
                                             REFERENCES async_jobs(id)
                                             ON DELETE SET NULL,
    extracted_fields            JSONB        NULL,
    uploaded_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_documents_extraction_status CHECK (
        extraction_status IN (
            'pending', 'classifying', 'extracting', 'complete', 'failed'
        )
    )
);

CREATE INDEX ix_documents_tenant_uploaded
    ON documents (tenant_id, uploaded_at DESC);

CREATE INDEX ix_documents_extraction_status
    ON documents (extraction_status)
    WHERE extraction_status IN ('classifying', 'extracting');
```

**Column-by-column contract (11 columns):**

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | `gen_random_uuid()` | PK |
| `tenant_id` | UUID | NOT NULL | — | FK → `tenants.id`, `ON DELETE CASCADE` (consistent with ADR-012 tenant isolation + cascading cleanup) |
| `original_filename` | VARCHAR(255) | NOT NULL | — | Filename the uploader supplied; sanitised at the upload endpoint (§6 Batch 2); UI-only — never used for storage keys |
| `storage_path` | VARCHAR(512) | NOT NULL | — | MinIO object key; format `{tenant_id}/{id}.{ext}`; ADR-013 compliant |
| `document_type` | VARCHAR(64) | NULL | — | Populated post-`classify_document`; `"invoice"`, `"receipt"`, … |
| `classification_confidence` | FLOAT | NULL | — | 0.0-1.0; populated with `document_type` |
| `extraction_status` | VARCHAR(32) | NOT NULL | `'pending'` | Governed by `ck_documents_extraction_status` |
| `extraction_job_id` | UUID | NULL | — | FK → `async_jobs.id`, `ON DELETE SET NULL` (jobs may be purged; row retains its audit) |
| `extracted_fields` | JSONB | NULL | — | `ExtractInvoiceOutput.model_dump()` on success |
| `uploaded_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | ADR-009 TZ-aware |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `NOW()` | Updated on status transitions (handler + Celery worker both write) |

**CHECK constraint (1):**

`ck_documents_extraction_status` — values restricted to the governed
set. Attempting to write any other value is a 22P02/23514-class
failure at the DB boundary; handler must not emit foreign statuses.

**Indexes (2):**

- `ix_documents_tenant_uploaded (tenant_id, uploaded_at DESC)` — the
  dashboard panel's primary query: *"list this tenant's recent
  uploads"*. Composite with `DESC` on `uploaded_at` so the top-N
  lookup is a single index range scan.
- `ix_documents_extraction_status` — **partial index** restricted to
  `('classifying', 'extracting')`. Ops-side queries (*"what is
  currently in flight?"*) are cheap; no index bloat for the common
  `'pending' | 'complete' | 'failed'` rows.

**Foreign keys (2):**

- `tenant_id → tenants.id ON DELETE CASCADE` — tenant purge removes
  their document rows; no orphans.
- `extraction_job_id → async_jobs.id ON DELETE SET NULL` — if the
  async job row is purged by a future TTL cleanup task, the document
  row persists with `extraction_job_id = NULL`. The `extracted_fields`
  JSONB still captures the result.

### §5.2 Pydantic models (new)

New module `app/schemas/doc_intelligence_schemas.py` hosts all ASP-04
Pydantic models. Existing inline schemas in `app/services/doc_intelligence.py`
migrate into this file as part of S-4; the service module imports them
back with no behavioural change.

```python
# app/schemas/doc_intelligence_schemas.py  (NEW)

from typing import Optional
from pydantic import BaseModel, ConfigDict


# --- existing (migrated from app/services/doc_intelligence.py) -----------

class ExtractDocumentOutput(BaseModel):
    """Generic document extraction output. Governed unchanged from
    pre-governance state for consumer contract lock."""
    model_config = ConfigDict(extra="ignore")
    fields:      dict
    tables:      list[dict]
    confidence:  float
    page_count:  int


class ClassifyDocumentOutput(BaseModel):
    """Document classification output. Governed unchanged."""
    model_config = ConfigDict(extra="ignore")
    doc_type:          str
    confidence:        float
    suggested_fields:  list[str]


# --- NEW (F-DOC-01) ------------------------------------------------------

class LineItem(BaseModel):
    """One line item on an invoice. All quantitative fields nullable —
    real invoices frequently omit unit_price or quantity."""
    model_config = ConfigDict(extra="ignore")
    description:  str
    quantity:     Optional[float] = None
    unit_price:   Optional[float] = None
    amount:       Optional[float] = None


class ExtractInvoiceOutput(BaseModel):
    """Invoice-specific extraction output.

    Directive-quoted shape (ASP-OUT-042 Q-6). All fields nullable
    because real invoices are inconsistent — LLM extracts what is
    present; missing fields return null, not errors.
    """
    model_config = ConfigDict(extra="ignore")
    vendor:          Optional[str]            = None
    invoice_number:  Optional[str]            = None
    invoice_date:    Optional[str]            = None
    due_date:        Optional[str]            = None
    line_items:      list[LineItem]           = []
    subtotal:        Optional[float]          = None
    tax_amount:      Optional[float]          = None
    total_amount:    Optional[float]          = None
    currency:        Optional[str]            = None
    payment_terms:   Optional[str]            = None
```

**`extra="ignore"` rationale.** Doc Intelligence outputs are LLM-
generated; the extraction prompt may emit additional fields on drift.
`extra="ignore"` lets retrieval succeed without 422-ing on minor LLM
variance; the handler post-processes the governed subset. Consistent
with ADR-033 for the generation service and BP-10 precedent.

**Date types — string not `date`.** `invoice_date` and `due_date` are
deliberately `Optional[str]` rather than `Optional[date]`. Real
invoices contain dates in dozens of formats (`"2026-01-15"`,
`"15 Jan 2026"`, `"Q1 2026"`, free-text). Pydantic `date` parsing
would 422 on the long tail; consumer-side normalisation is the
governed path.

### §5.3 Upload-endpoint payload model (new)

Request/response shape is fully specified in §6 (Batch 2). For §5
completeness, the governed models are:

```python
# app/schemas/doc_intelligence_schemas.py  (NEW, continued)

class DocumentUploadResponse(BaseModel):
    """Response for POST /api/v1/ai/documents."""
    model_config = ConfigDict(extra="forbid")   # response contract — strict
    document_id:       str                       # UUID as string
    storage_path:      str                       # MinIO object key (tenant-prefixed)
    tenant_id:         str                       # echoed from auth (NOT payload)
    original_filename: str
    uploaded_at:       str                       # ISO-8601 UTC
```

Request is `multipart/form-data` — not a Pydantic model at the FastAPI
boundary (`File(...)` + `Form(...)` params). See §6 for wire format.

### §5.4 Alembic migration 0028

```python
# alembic/versions/0028_add_documents_table.py

"""ASP-FEAT-ASP-04 v1.0 — documents registry table.

Revision ID: 0028
Revises:     0027
Create Date: 2026-04-21

First DDL migration since 0023. Adds `documents` per ASP-FEAT-ASP-04
v1.0 §5. No prompt rows in this migration — those land in 0029.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=True),
        sa.Column("classification_confidence", sa.Float, nullable=True),
        sa.Column("extraction_status", sa.String(32), nullable=False,
                  server_default="pending"),
        sa.Column("extraction_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("extracted_fields", JSONB, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE",
            name="fk_documents_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_job_id"], ["async_jobs.id"], ondelete="SET NULL",
            name="fk_documents_extraction_job",
        ),
        sa.CheckConstraint(
            "extraction_status IN ('pending','classifying','extracting',"
            "'complete','failed')",
            name="ck_documents_extraction_status",
        ),
    )
    op.create_index(
        "ix_documents_tenant_uploaded", "documents",
        ["tenant_id", sa.text("uploaded_at DESC")],
    )
    op.create_index(
        "ix_documents_extraction_status", "documents",
        ["extraction_status"],
        postgresql_where=sa.text(
            "extraction_status IN ('classifying','extracting')"),
    )


def downgrade():
    op.drop_index("ix_documents_extraction_status", table_name="documents")
    op.drop_index("ix_documents_tenant_uploaded", table_name="documents")
    op.drop_table("documents")
```

**Fresh-DB round-trip gate (ADR-029).** Pre-merge: `alembic upgrade
head` on an empty DB must reach 0028 without error; `alembic downgrade
0027` must rollback cleanly. CI enforces.

### §5.5 Alembic migration 0029 (prompt seed — deferred)

Migration 0029 seeds the `extract_invoice` prompt row. Full SQL
surfaces in §9 (Batch 2) alongside prompt design. Structural preview:

```python
# alembic/versions/0029_seed_extract_invoice_prompt.py
# revision = "0029"; down_revision = "0028"
# service_type='doc_intelligence', task='extract_invoice',
# caller_module='*', maturity_level='*', version=1,
# is_active=TRUE, ab_variant=NULL.
```

Reach check (G-PROMPT-REACH) at `(*, *)` matches the existing
`extract_document`/`classify_document` pattern — reachable from any
caller at any maturity via fallback chain level 4.

### §5.6 SQLAlchemy ORM model

```python
# app/models/db_models.py — APPEND at end

class Document(Base):
    """ASP-FEAT-ASP-04 v1.0 §5 — documents registry."""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    original_filename = Column(String(255), nullable=False)
    storage_path      = Column(String(512), nullable=False)
    document_type     = Column(String(64),  nullable=True)
    classification_confidence = Column(Float, nullable=True)
    extraction_status = Column(String(32),  nullable=False,
                               default="pending")
    extraction_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("async_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    extracted_fields  = Column(JSONB, nullable=True)
    uploaded_at       = Column(DateTime(timezone=True),
                               nullable=False, default=utcnow)
    updated_at        = Column(DateTime(timezone=True),
                               nullable=False, default=utcnow,
                               onupdate=utcnow)

    tenant = relationship("Tenant", back_populates="documents")

    __table_args__ = (
        CheckConstraint(
            "extraction_status IN ('pending','classifying','extracting',"
            "'complete','failed')",
            name="ck_documents_extraction_status",
        ),
        Index("ix_documents_tenant_uploaded",
              "tenant_id", text("uploaded_at DESC")),
        # partial index lives in the migration; ORM doesn't need to
        # replicate its WHERE clause.
    )
```

`Tenant` gains `documents = relationship("Document",
back_populates="tenant", cascade="all, delete-orphan")`.

### §5.7 Pre-write gate — G-1..G-8 at Batch 1 close

| Gate | Status | Notes |
|---|---|---|
| G-1 Schema | ✓ § 5.1 authored verbatim to SQL + ORM | |
| G-2 Types | ✓ § 5.1 column table; JSONB / TIMESTAMPTZ / FLOAT / VARCHAR all live-DB compatible | |
| G-3 Contract | Pending §6 (Batch 2) | |
| G-4 Audit (CHECK) | ✓ `ck_documents_extraction_status` in both migration + ORM | |
| G-5 Migration | ✓ 0028 (DDL) authored; 0029 (prompt) structural preview only — final SQL in §9 Batch 2 | |
| G-6 Frontend | Pending §11 (Batch 3) / S-8 | |
| G-7 Dependency | Noted: `app/schemas/doc_intelligence_schemas.py` (new), `app/api/documents.py` (new), `app/ui/dashboard.py` (new), `app/templates/`, `app/static/` | |
| G-8 Prompt Reach | Pending migration 0029 authoring in §9 Batch 2 | |

---

**End of Batch 1 (§1–§5).** Batch 2 (§6 API Contract · §7 Request/Response
Detail · §8 Caller Integration · §9 LLM/Prompt Design · §10 Security)
follows on review.

**Awaiting Architect review before Batch 2 authoring.** Points of
particular interest for the review pass:

1. §4.2 — `classify_document` tier upgrade to `enhanced` — is this
   acceptable or should classification stay on `standard` (Haiku) and
   only `extract_invoice` use Sonnet?
2. §5.1 — the `extraction_status` CHECK set is
   `{pending, classifying, extracting, complete, failed}`. Is this
   granular enough, or would you prefer finer states (e.g.
   `classified` between `classifying` and `extracting`)?
3. §5.2 — `invoice_date` / `due_date` as `Optional[str]` (directive
   verbatim) vs `Optional[date]` — flagging the format-tolerance
   trade-off for confirmation.
4. §5.6 — `Document` ORM model references `Tenant.documents`
   relationship with `cascade="all, delete-orphan"`. Consistent with
   existing `async_jobs`/`cost_events` relationships or divergent?
