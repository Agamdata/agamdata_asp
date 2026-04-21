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

**End of Batch 1 (§1–§5).** Batch 2 follows.

**Batch 1 review points (no blocking rulings issued in ASP-OUT-047 —
taken as tacit accept; the four review questions remain flagged for
Architect confirmation at Batch 3 close if different rulings are
desired).** Batch 2 authored against Batch 1 as written.

---

## §6 API Contract

Two new public surfaces ship in v1.0: the multipart upload endpoint
(S-3) and the dashboard UI surface (S-8). The existing
`POST /api/v1/ai/invoke` and `GET /api/v1/ai/jobs/{job_id}` contracts
are **governed unchanged** for the three doc tasks — no wire-format
changes; the spec formalises the existing contract for consumer lock.

### §6.1 New endpoint — `POST /api/v1/ai/documents`

Zone 2 Shared Contract. Multipart upload for PDFs. Follows all
ASP-FEAT-ASP-00 v1.0 Gateway conventions: `X-ASP-API-Key` auth,
RFC 7807 error envelope, per-tenant rate limit (inherits global
rate-limiter config), structured log emission.

**Request shape:**

```
POST /api/v1/ai/documents HTTP/1.1
Host: asp.pilot.internal
X-ASP-API-Key: asp_<prefix12>_<secret32>
Content-Type: multipart/form-data; boundary=<boundary>
X-Request-Id: <optional — Gateway mints one if absent>

--<boundary>
Content-Disposition: form-data; name="file"; filename="acme-invoice.pdf"
Content-Type: application/pdf

<raw bytes — PDF>
--<boundary>
Content-Disposition: form-data; name="document_type_hint"

invoice
--<boundary>--
```

**Form parts (governed):**

| Name | Required | Type | Notes |
|---|---|---|---|
| `file` | yes | PDF binary (`application/pdf`) | Max 20 MB in v1.0 (rate-limiter-adjacent config `ASP_DOC_UPLOAD_MAX_MB`, default `20`). Rejected with 413 if exceeded. |
| `document_type_hint` | no | `str` | Advisory hint for the `classify_document` downstream call. Accepted values: `"invoice"`, `"receipt"`, `"contract"`, `"other"`, or omitted. Does not bypass classification; the LLM may override. |

**Note:** `tenant_id` is **not** a form part. It is extracted from the
authenticated API key by `verify_api_key` (the request's authoritative
tenant identity — ADR-022 leak-safety). Including a `tenant_id` form
part is silently ignored.

**Success response (201 Created):**

```http
HTTP/1.1 201 Created
Content-Type: application/json
X-Request-Id: <request-id>

{
  "document_id": "c5f2c8f0-9f1e-4b3a-8e2f-1d4c7a9b3e5f",
  "storage_path": "a9f0.../c5f2c8f0-9f1e-4b3a-8e2f-1d4c7a9b3e5f.pdf",
  "tenant_id": "a9f03b2c-7d4e-4c1f-b2a9-0e8f6d5c3a7b",
  "original_filename": "acme-invoice.pdf",
  "uploaded_at": "2026-04-21T14:32:11.284Z"
}
```

Body shape is the `DocumentUploadResponse` Pydantic model (§5.3).
`extra="forbid"` applies on the response — any drift from this shape
is a regression.

**Error responses (RFC 7807):**

| HTTP | `type` | Trigger |
|---|---|---|
| 400 | `/errors/invalid-multipart` | Missing `file` part; malformed boundary |
| 401 | `/errors/unauthorized` | Missing or invalid `X-ASP-API-Key` |
| 413 | `/errors/payload-too-large` | `file` exceeds `ASP_DOC_UPLOAD_MAX_MB` |
| 415 | `/errors/unsupported-media-type` | `file` Content-Type is not `application/pdf` |
| 422 | `/errors/validation` | `document_type_hint` is non-string or not in accepted set |
| 500 | `/errors/internal` | MinIO write failure; DB write failure (after asyncpg port per S-1) |

All errors follow the standard RFC 7807 envelope established by
ASP-FEAT-ASP-00 v1.0: `{type, title, status, detail, instance,
request_id}`.

**Side effects on 201 success:**

1. Bytes written to MinIO at `asp-documents/{tenant_id}/{document_id}.pdf`
   (ADR-013 tenant-prefixed storage path).
2. One INSERT into `documents` — all required columns populated;
   `extraction_status='pending'`; `document_type`,
   `classification_confidence`, `extracted_fields`, `extraction_job_id`
   all NULL at upload time (populated by downstream classify / extract
   calls).
3. `emit_cost_event` called with `service_type='doc_intelligence'`,
   `task='upload'`, `cost_usd=0.0` (upload itself has no LLM cost;
   the row exists for audit/rate-limit accounting). ADR-006 applies —
   cost emission wrapped in `try/except` per S-6.
4. Structlog event `asp_doc_upload_succeeded` with `tenant_id`,
   `document_id`, `storage_path`, `original_filename`, `size_bytes`.

### §6.2 Governed — `POST /api/v1/ai/invoke` for doc tasks

Existing Gateway endpoint; no change to the wire contract. Three
doc tasks are reachable under `service_type="doc_intelligence"`:

| `task` | `payload` shape | Output | Status |
|---|---|---|---|
| `classify_document` | `{file_key: str}` | `ClassifyDocumentOutput` (§5.2) | Existing — governed unchanged |
| `extract_document` | `{file_key: str}` | `ExtractDocumentOutput` (§5.2) | Existing — governed unchanged |
| `extract_invoice` | `{file_key: str}` | `ExtractInvoiceOutput` (§5.2) | **NEW** (S-4) |

**`file_key` contract.** Must equal the `storage_path` returned by
§6.1. The Gateway validates that the `file_key` begins with
`{tenant_id}/` before enqueueing — if the prefix does not match the
authenticated tenant, respond 403 `/errors/forbidden` (NOT 404; the
key format is not sensitive, and this signals the contract violation
clearly to PAP rather than leaking as a silent "not found"). *This is
a deliberate deviation from the standard cross-tenant 404 rule
(CLAUDE.md §Known Gotchas) — the `file_key` contract is a
self-constructed value, not a resource lookup, so contract-violation
semantics fit better than existence-leak semantics.*

**Async response shape (unchanged):**

```json
{
  "request_id": "...",
  "job_id": "...",
  "status": "queued",
  "status_url": "/api/v1/ai/jobs/<job_id>"
}
```

### §6.3 Governed — `GET /api/v1/ai/jobs/{job_id}`

Existing endpoint; no change. Dashboard panel polls here; success
payload for the three doc tasks carries the task's output model as
the `result` field.

### §6.4 New UI endpoints (S-8)

Zone 2 UI surface; same `ai-service` container. Authenticated via the
same `X-ASP-API-Key` header OR via an authenticated-session cookie
for browser sessions (cookie mechanics covered in §7.5 once the S-8
session handshake is confirmed).

| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard/doc-intelligence` | Renders the two-panel review page (Jinja `doc_intelligence.html`) |
| GET | `/dashboard/doc-intelligence/upload` | HTMX partial — upload form |
| POST | `/dashboard/doc-intelligence/upload` | HTMX-submit target; proxies to §6.1 under the session auth; returns `_review_panel.html` partial on success |
| GET | `/dashboard/doc-intelligence/documents/{document_id}` | HTMX partial — review panel for a specific document |
| GET | `/dashboard/doc-intelligence/documents/{document_id}/pdf` | Streams the PDF bytes from MinIO (tenant-scoped — 403 on mismatch) |

**Why separate UI endpoints rather than CORS from a dashboard SPA?**
Per ASP-OUT-042 Q-5 Option D ruling: zero build tooling; single
Docker service; server-rendered Jinja + HTMX. CORS surface is not
introduced; the UI is same-origin with the API.

### §6.5 `GET /api/v1/ai/capabilities` surface updates

The existing capabilities endpoint (ASP-FEAT-ASP-00 v1.0) adds:

- `doc_intelligence` → `["classify_document", "extract_document",
  "extract_invoice"]` under the `services` map. Emitted by the
  existing `SERVICE_CAPABILITIES` aggregation (no change to that
  file's logic — the VALID_TASKS set in `app/services/doc_intelligence.py`
  is the source).

- `TASK_SCHEMA_MODELS` entries registered for all three doc tasks
  (S-5). Each → a simple `{file_key: str}` Pydantic model exposed via
  `GET /api/v1/ai/schemas/doc_intelligence/<task>` per ADR-030.

### §6.6 Error matrix (internal + external)

Internal-only failures (never caller-visible):

| Condition | Emits | Behaviour |
|---|---|---|
| MinIO 5xx on upload write | `asp_doc_upload_storage_failure` structlog + 500 RFC 7807 | Document row NOT created; bytes not persisted; caller retries |
| DB write failure on `documents` INSERT after MinIO succeeded | `asp_doc_upload_db_failure` + 500; bytes ARE in MinIO | Orphan blob cleanup is ops-responsibility in v1.0. Future v1.1 will add a reaper task. |
| MinIO 5xx on worker-side download | `asp_doc_job_failed` with `reason=storage_download` | Job status → `failed`; document row `extraction_status='failed'` |
| LLM 529/Overloaded | handled by existing `llm_call_with_retry` | Transparent retry; no external visibility |

External visibility to consumers (PAP, LogiCRM, UI):

| Condition | Caller sees |
|---|---|
| Successful upload | 201 + `DocumentUploadResponse` |
| Missing collection / prompt | 503 `/errors/service-unavailable` (same pattern as RAG `RAGCollectionMissingError`); `remediation` field populated |
| Tenant isolation violation on file_key | 403 `/errors/forbidden` |
| Cross-tenant document fetch | 404 `/errors/not-found` (never 403 — consistent with the rest of the API) |

### §6.7 Capabilities-exclusion decisions (governed)

RAG (ASP-02), Cost Meter (ASP-08), Cost Aggregator (ASP-10), Model
Router (ASP-11), Ontology Manager (ASP-12) remain Zone 1 per
ADR-001 — **not** affected by this spec. Doc Intelligence joins the
`capabilities` surface alongside Generation and NLP. Dashboard
Intelligence (ASP-13) is already in capabilities for its four
existing tasks; the dashboard panel is a UI surface, not a new
task — no `capabilities` change for S-8.

---

## §7 Request / Response Detail

### §7.1 Upload request — wire format

Per §6.1. Additional governance on the upload implementation:

- **FastAPI endpoint signature:**

  ```python
  # app/api/documents.py  (NEW)

  @router.post("/ai/documents", status_code=201,
               response_model=DocumentUploadResponse)
  async def upload_document(
      request: Request,
      file: UploadFile = File(...),
      document_type_hint: Optional[str] = Form(default=None),
      tenant=Depends(verify_api_key),
  ) -> DocumentUploadResponse:
      ...
  ```

- **UUID generation.** `document_id` is generated server-side via
  `uuid.uuid4()` at the endpoint (NOT client-suppliable). Mirrors the
  `async_jobs.id` pattern.

- **Storage-path derivation.** `{tenant_id}/{document_id}.pdf`.
  Tenant ID is the authoritative value from `tenant.id` (the Tenant
  object returned by `verify_api_key`), NOT from any form part.

- **Content-type validation.** `file.content_type` checked against
  `{"application/pdf"}`. Other PDF-like types (`application/x-pdf`,
  `application/acrobat`) NOT accepted in v1.0 — tighten contract,
  document explicitly.

- **Filename sanitisation.** `original_filename` taken from
  `file.filename` with:
  - Path separators stripped (`/`, `\`, `..`) to prevent directory
    traversal in downstream rendering.
  - Truncation to 255 chars (matches DB column width).
  - Non-UTF-8 bytes rejected with 422.

- **Size check.** `file.size` (FastAPI 0.115 exposes on UploadFile)
  > `settings.ASP_DOC_UPLOAD_MAX_MB * 1024 * 1024` → 413 before the
  bytes are read into memory.

### §7.2 `DocumentUploadResponse` model

```python
# app/schemas/doc_intelligence_schemas.py

class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")   # response contract — strict
    document_id:       str                       # UUID as string
    storage_path:      str                       # MinIO object key (tenant-prefixed)
    tenant_id:         str                       # echoed from auth (NOT payload)
    original_filename: str
    uploaded_at:       str                       # ISO-8601 UTC
```

`extra="forbid"` on the response model is deliberate — response
contracts are the strict side of ADR-008. Request/payload models for
doc tasks use `extra="ignore"` per ADR-033.

### §7.3 Invoke-path request shape for doc tasks

The Gateway accepts:

```json
{
  "service_type": "doc_intelligence",
  "task": "extract_invoice",
  "caller_module": "playwright_runner",
  "tenant_id": "a9f03b2c-...",
  "payload": {
    "file_key": "a9f03b2c-.../c5f2c8f0-...pdf"
  },
  "quality_tier": "enhanced",
  "user_context": {"user_id": "u-demo", "role": "analyst",
                   "maturity_level": "L2"}
}
```

Immediate response (202 per existing async contract):

```json
{
  "request_id": "req-01HXY...",
  "job_id": "job-01HXY...",
  "status": "queued",
  "status_url": "/api/v1/ai/jobs/job-01HXY..."
}
```

### §7.4 Job-result shapes (polled at `/api/v1/ai/jobs/{job_id}`)

On `status='completed'`, the `result` field is the task's output
model:

```jsonc
// classify_document
{
  "request_id": "...",
  "job_id": "...",
  "status": "completed",
  "result": {
    "doc_type": "invoice",
    "confidence": 0.94,
    "suggested_fields": ["vendor", "invoice_number", "total_amount"]
  }
}

// extract_invoice
{
  "request_id": "...",
  "job_id": "...",
  "status": "completed",
  "result": {
    "vendor": "Acme Corporation",
    "invoice_number": "INV-0042",
    "invoice_date": "2026-03-15",
    "due_date": "2026-04-14",
    "line_items": [
      {"description": "Consulting hours",
       "quantity": 20.0, "unit_price": 150.0, "amount": 3000.0}
    ],
    "subtotal": 3000.0,
    "tax_amount": 540.0,
    "total_amount": 3540.0,
    "currency": "USD",
    "payment_terms": "Net 30"
  }
}
```

On `status='failed'`, the `error` field carries an RFC 7807
envelope — same shape as top-level 5xx responses so consumers have a
single error-handling code path.

### §7.5 Session / cookie mechanics for the dashboard UI

UI calls use the same `X-ASP-API-Key` header in v1.0 pilot (headers
are set by a small inline JavaScript snippet on the dashboard page
that reads from `localStorage.ASP_API_KEY`). **No server-side session
cookie in v1.0** — the pilot demo is ops-triggered with a known key.

A future v1.1 will formalise a session-cookie handshake if the
dashboard is exposed to non-ops users. Scope boundary preserves the
pilot demo with minimum auth-surface drift.

### §7.6 Structlog events — full catalogue

Every Celery task transition emits a structlog event. Additions to
the registry:

| Event | Emitter | Fields |
|---|---|---|
| `asp_doc_upload_succeeded` | upload endpoint on 201 | `tenant_id`, `document_id`, `storage_path`, `original_filename`, `size_bytes` |
| `asp_doc_upload_storage_failure` | upload endpoint on MinIO 5xx | `tenant_id`, `error`, `reason="storage_write"` |
| `asp_doc_upload_db_failure` | upload endpoint on post-MinIO DB insert failure | `tenant_id`, `document_id_pending`, `storage_path`, `error` |
| `asp_doc_job_queued` | enqueue path (existing, extended with `document_id`) | `tenant_id`, `job_id`, `task`, `document_id`, `file_key` |
| `asp_doc_job_running` (NEW — S-7) | Celery task entry | `tenant_id`, `job_id`, `task`, `document_id` |
| `asp_doc_job_completed` (NEW — S-7) | Celery task success exit | `tenant_id`, `job_id`, `task`, `document_id`, `duration_ms`, `input_tokens`, `output_tokens` |
| `asp_doc_job_failed` (NEW — S-7) | Celery task exception | `tenant_id`, `job_id`, `task`, `document_id`, `error`, `reason` |
| `asp_doc_classify_confidence_low` | `classify_document` handler when `confidence < 0.5` | `tenant_id`, `document_id`, `doc_type`, `confidence` |

All events inherit `request_id` and `caller_module` via structlog
contextvars per the ASP-FEAT-ASP-00 v1.0 convention.

---

## §8 Caller Integration Guide

### §8.1 Primary caller — the ASP-13 dashboard panel (S-8)

Sole interactive caller in v1.0. The browser flow is:

```
[engineer] --selects PDF--> [dashboard upload form]
     --HTMX POST multipart--> [POST /dashboard/doc-intelligence/upload]
     --server-side proxy--> [POST /api/v1/ai/documents]
     --returns JSON document_id--> [server renders _upload_success.html]
     --HTMX swap into #upload-slot--> [dashboard]

[dashboard] --HTMX GET classify--> [POST /api/v1/ai/invoke classify_document]
     --202 + job_id--> [dashboard polls GET /jobs/{job_id} every 2s]
     --status=completed--> [HTMX swap into #classify-slot → badge]

[dashboard] --HTMX GET extract--> [POST /api/v1/ai/invoke extract_invoice]
     --202 + job_id--> [poll]
     --status=completed--> [HTMX swap into #review-slot → _review_panel.html]
```

**Polling cadence governance.**
- Default 2-second interval for the demo (handler-agnostic; handled
  by HTMX `hx-trigger="every 2s"` on the polling partial).
- Maximum 45 seconds end-to-end before the UI shows a "still
  extracting…" notice. This is **UI behaviour only** — the job runs
  until Celery's own timeout; polling just stops.
- No server-side rate limit on polling — polling hits the existing
  `GET /api/v1/ai/jobs/{job_id}` which is **excluded** from the
  global rate limiter per ASP-FEAT-ASP-00 v1.0 (§10).

### §8.2 Programmatic callers — PAP + LogiCRM

PAP and LogiCRM can invoke the three doc tasks directly via the
Gateway — same async contract, same `POST → 202 → poll` pattern used
for `doc_intelligence` tasks already. No special handling required
for the `extract_invoice` addition; it is a standard task registration.

**Migration path for existing callers.** None required. Consumer code
that already hits `classify_document` / `extract_document` continues
to work. To use `extract_invoice`, callers send `task="extract_invoice"`
with `payload={"file_key": "<upload-returned storage_path>"}`.

### §8.3 Upload-first vs direct-file-key contract

Historically the three doc tasks accepted any `file_key` the caller
chose. Per S-3 + Q-3 ruling, v1.0 mandates the upload endpoint as the
**canonical path** for getting a `file_key`:

1. Preferred: `POST /api/v1/ai/documents` → returns `storage_path`;
   use that as `file_key`.
2. Legacy / bypass: direct caller-constructed `{tenant_id}/<opaque>.pdf`
   still accepted — the tenant-prefix validation is the only gate.

The upload-first path produces a tracked `documents` row; legacy
bypass does NOT (no `documents` row; async_jobs still tracks the
task). Consumers that want per-document audit, status queries, or
dashboard rendering MUST use the upload path. Consumers that just
want a one-shot extract-and-forget may still use direct file keys.

### §8.4 Error-path semantics for callers

| Condition | HTTP | Consumer action |
|---|---|---|
| Missing upload (file_key not in MinIO) | 404 `/errors/not-found` on the invoke | Caller re-uploads OR uses a different key |
| Tenant-prefix mismatch on file_key | 403 `/errors/forbidden` on the invoke | Caller's bug — check authentication context matches the tenant they believe they're using |
| Classification confidence < 0.5 | 200 + `result` with low confidence; `asp_doc_classify_confidence_low` structlog warning | Caller's decision — retry with `document_type_hint`, or surface to user for manual review |
| Extraction returns all-nullable output | 200 + `result` with every field None; confidence low | Same as above — real invoices may be pathological; no 5xx |
| Worker-side LLM failure | Job `status='failed'` + `error` envelope on polling | Caller retries OR surfaces to user |
| Worker-side DB write failure (post-S-1 fix) | Job `status='failed'` + `error` envelope | **Should be rare after S-1.** If persistent, ops alert via `asp_doc_job_failed` structlog. |

### §8.5 Rate-limit and cost contract

- Upload endpoint (`POST /api/v1/ai/documents`): subject to the
  global per-tenant rate limiter (ASP-FEAT-ASP-00 v1.0 §6) —
  default 60 requests/minute/tenant.
- Invoke endpoint for doc tasks: subject to the same global rate
  limiter.
- Job polling (`GET /jobs/...`): excluded from rate limiter.
- UI endpoints (`GET /dashboard/...`): excluded from rate limiter
  (interactive pilot).

Cost emission per doc task:

| Task | Cost model | Emission |
|---|---|---|
| Upload | `cost_usd=0.0` | Logged for audit; no LLM |
| `classify_document` | Haiku input+output tokens | Existing pattern |
| `extract_document` | Haiku input+output tokens | Existing pattern |
| `extract_invoice` | **Sonnet** input+output tokens | New emission; quality-tier differentiated rate |

All emissions wrapped in `try/except` per ADR-006 (S-6 fix).

### §8.6 Consumer visibility of the new `documents` table

Internal to ASP. Not exposed via any API surface in v1.0. Dashboard
panel reads it server-side via the UI router; callers that want
document audit history call the invoke endpoint's output
(`extracted_fields` is the authoritative per-call record) OR wait for
v1.1 which may expose a `GET /api/v1/ai/documents` list endpoint if
demand emerges.

---

## §9 LLM and Prompt Design

### §9.1 `classify_document` (existing; quality tier upgrade only)

Prompt unchanged from the row seeded in migration `0002`. Invoked
under `quality_tier="enhanced"` for the demo flow; the LLM is Claude
Sonnet via ASP-11 Model Router. No migration change to the prompt
row — the tier upgrade is a **request-layer decision**, not a prompt
redefinition.

**Reach governance.** The existing row is seeded at
`caller_module="*"`, `maturity_level="*"` (verified against the live
DB at Batch 2 authoring time). G-PROMPT-REACH matrix passes for every
caller permutation; no wildcard-fix migration required (unlike
F-03-02 which triggered ASP-OUT-051).

### §9.2 `extract_document` (existing; unchanged)

Prompt unchanged. Standard tier (Haiku). Not on the demo path.
Retained in VALID_TASKS for LogiCRM legacy callers.

### §9.3 `extract_invoice` (NEW — migration 0029)

New prompt row seeded in migration 0029 (prompt-only, no DDL).
Directive-quoted structure per §9.3 below.

**System prompt:**

```
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
```

**User prompt template:**

```
{document_text}
```

Minimal by design — the system prompt specifies the contract; the
user prompt is just the OCR'd text. No context placeholders beyond
the document text itself.

### §9.4 OCR pipeline

PDFs are OCR'd in the Celery worker before the LLM call. Governed
implementation: `pdftotext` (from `poppler-utils`, already in the
Docker image) as the default; falls back to `pytesseract` if
`pdftotext` returns empty text (common for scanned-image PDFs).

OCR output is capped at 50K characters before prompt injection. If
the OCR output exceeds the cap:
- Structlog warning `asp_doc_ocr_truncated` with the original length.
- Truncation is tail-truncation — the invoice total is usually at the
  end; keeping the tail preserves the most commercially-relevant
  data.

OCR failure (both `pdftotext` and `pytesseract` return empty) is a
job-failure with `reason="ocr_empty"`. No LLM call is made in that
case.

### §9.5 Migration 0029 — prompt seed

```python
# alembic/versions/0029_seed_extract_invoice_prompt.py
# revision = "0029"; down_revision = "0028"

_INSERT = """
    INSERT INTO prompt_templates
      (service_type, task, caller_module, maturity_level, version,
       is_active, ab_variant, system_prompt, user_prompt_template)
    VALUES
      ('doc_intelligence', 'extract_invoice', '*', '*', 1, TRUE, NULL,
       :sys, :usr)
"""
```

**Reach-gate contract for 0029 (per expanded G-PROMPT-REACH).** The
row is seeded at `caller_module='*'`, `maturity_level='*'` — the
broadest pattern. Reach probes must verify:

| Caller | Maturity | Expected |
|---|---|---|
| `playwright_runner` | L2 | PASS → row `(*, *)` |
| `test_generator` | L2 | PASS → row `(*, *)` |
| `*` | L2 | PASS → row `(*, *)` |

Three probes minimum — fewer than F-03-02's 20 because the wildcard
seed needs no caller-specific rows. If we later add a caller-specific
override, the probe matrix expands per the playbook.

### §9.6 Prompt token-budget governance

- `classify_document` (existing): `max_tokens=256` — short output
  (doc_type + confidence + suggested_fields list).
- `extract_document` (existing): `max_tokens=2048`.
- `extract_invoice` (new): `max_tokens=4096`. Real invoices with
  many line items can approach 3K output tokens; 4K leaves headroom.
  Sonnet context window comfortably handles 50K OCR input + 4K output.

All three tasks honour `DEFECT-017` truncation guard — if
`stop_reason='max_tokens'`, emit `generation_truncated` structlog
and return 500 with remediation hint.

### §9.7 Prompt change-control

Changes to the `extract_invoice` prompt after v1.0 require:
- A new migration (not an UPDATE of the existing row).
- Deactivation of the prior row (`is_active=FALSE`) in the same migration.
- Reach re-verification per the expanded G-PROMPT-REACH rule
  (minimum 3 probes for the wildcard seed).
- OpenAPI snapshot refresh if the payload/output shape changes.

No change-control is required for tier changes (quality_tier is a
request-layer decision, not persisted in prompt_templates).

---

## §10 Security Requirements

### §10.1 Tenant isolation — three layers

**Layer 1 (primary) — API-key tenant scoping.** `verify_api_key`
returns the Tenant object; every downstream write uses `tenant.id`
exclusively. No form part, no URL path parameter, no JSON body field
can override the authenticated tenant.

**Layer 2 (defence-in-depth) — storage-path prefix.** Every MinIO
object key begins with `{tenant_id}/`. The upload endpoint enforces
this by construction (the endpoint never reads `tenant_id` from any
client-controllable surface). The Celery worker validates the
`file_key` prefix against the invoke request's `tenant_id` before
downloading. Cross-tenant file_keys are rejected with 403.

**Layer 3 (audit) — `documents.tenant_id` FK.** Every row in the
`documents` table carries the owning tenant. Cross-tenant SELECTs are
impossible without DB-level admin access (which is out of scope for
application-layer security). The `ON DELETE CASCADE` FK ensures
tenant purge removes all their documents atomically.

**Cross-tenant probe contract (AC in Batch 3).** Seed a document as
tenant A, then attempt every consumer-facing operation as tenant B:
- `GET /jobs/{job_id}` for A's job → 404 (not 403)
- `POST /api/v1/ai/invoke extract_invoice` with A's file_key under
  B's key → 403
- `GET /dashboard/.../pdf` with A's document_id under B's session →
  404

### §10.2 Upload-endpoint attack surface

Inputs: multipart form with one file and one optional string.
Defences:

| Threat | Defence |
|---|---|
| Directory traversal via filename | Path separators stripped at §7.1; storage path is server-derived |
| Filename too long / non-UTF-8 | 255-char truncation; 422 on decode failure |
| Content-type spoofing | `file.content_type` whitelist (`application/pdf` only); MIME sniffing of the first 4 bytes (`%PDF`) as secondary check |
| DoS via huge file | Size check before bytes read (FastAPI's UploadFile streaming); 413 on overflow |
| DoS via many small files | Global per-tenant rate limit applies to the upload endpoint |
| Malformed PDF that crashes OCR | `pdftotext` + `pytesseract` both wrapped in try/except inside the Celery worker; ocr-empty failure is job-status-failed, not worker-crash |
| Embedded JavaScript in PDF | NOT executed — `pdftotext` does not evaluate scripts; `pdf.js` renders on browser side with its own sandbox. Out-of-scope for explicit hardening in v1.0; flagged for v1.1 if a security audit surfaces concrete attack paths |

### §10.3 Dashboard UI hardening

Jinja templates use Jinja's default autoescape (HTML-escaped output
for all `{{ }}` interpolations). The review panel renders extracted
fields directly from the LLM output; HTMX swaps arrive as HTML so
Jinja escaping protects against any injection via crafted invoice
content (e.g., vendor names containing `<script>` tags).

`pdf.js` runs client-side; the PDF bytes stream from our origin, so
the browser's own same-origin policy protects against exfiltration
via cross-origin PDF loads.

No `eval()`, no `innerHTML` assignment from user-controllable strings
in `doc_review.js`. All DOM updates go through HTMX's governed swap
targets.

**CSP (governed).** `ai-service` adds the following CSP header on
`GET /dashboard/*` responses:

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' https://unpkg.com https://cdnjs.cloudflare.com;
  style-src 'self' 'unsafe-inline' https://unpkg.com;
  img-src 'self' data:;
  connect-src 'self';
  object-src 'none';
  frame-ancestors 'none';
```

HTMX and pdf.js are loaded from `unpkg.com` and `cdnjs.cloudflare.com`
respectively (pinned versions). `'unsafe-inline'` on `style-src` is
the pragmatic concession for Jinja-inlined styles; tightening is a
v1.1 item.

### §10.4 Embedding / data-handling

OCR text is transient — never persisted outside the Celery task
lifespan. The `documents.extracted_fields` JSONB carries only the
governed output schema (no raw OCR text).

LLM calls send OCR text to Anthropic; the output is stored in
`documents.extracted_fields`. Per ADR-022 / ADR-013, tenant data
boundaries are respected — no cross-tenant leakage in the LLM layer
because one job = one tenant = one file = one LLM request.

Structlog events do NOT log OCR text or extracted field contents —
only metadata (`tenant_id`, `document_id`, `confidence`,
`duration_ms`). The PII-heavy axes (vendor names, invoice numbers,
amounts) stay in the DB row, not in log streams.

### §10.5 No new auth surface

The upload endpoint uses the same `X-ASP-API-Key` auth as every
other Gateway endpoint. No new mechanism. No session cookie in v1.0.
Dashboard UI uses the same API key via inline JS (§7.5) — the key is
NOT stored in a cookie; it is re-read from `localStorage` on each
interaction. If a user clears localStorage, they re-enter the key.

### §10.6 ADR compliance

| ADR | Requirement | This spec's compliance |
|---|---|---|
| ADR-001 | Zone classification | ASP-04 / ASP-13 task surfaces Zone 2; Cost Meter, Model Router, Prompt Registry remain Zone 1 |
| ADR-006 | Cost emission resilience | S-6 wraps emission in `try/except` |
| ADR-008 | Pydantic `extra="forbid"` | Applied to response models (`DocumentUploadResponse`); `extra="ignore"` on LLM outputs per ADR-033 |
| ADR-009 | TZ-aware timestamps | `uploaded_at`, `updated_at` both TIMESTAMPTZ |
| ADR-010 | Structlog everywhere | S-7 emits three transition events; §7.6 catalogue |
| ADR-012 | Tenant isolation on every write | Three-layer enforcement per §10.1 |
| ADR-013 | Tenant-prefixed storage paths | Enforced by construction in upload endpoint |
| ADR-022 | Three-zone ownership model | ASP-04 is Zone 2 Shared Contract; dashboard panel UI is Zone 2 |
| ADR-026.2 | Four-way governance sync | Every spec-touching commit runs sha256 parity across repo + 00-index + 00-index/communication + 01-master |
| ADR-028 | Async-job pattern | Existing `async_jobs` + job_id + polling contract preserved |
| ADR-029 | Fresh-DB round-trip gate | Migrations 0028 (already applied P1 fix), 0029 (new seed) both pass |
| ADR-030 | Capabilities + schemas endpoints | S-5 registers all three doc tasks |
| ADR-032 | New-format API keys | Upload endpoint uses same `verify_api_key` flow |
| ADR-033 | Request-model `extra="ignore"` | Applied to `ExtractInvoiceOutput`, `LineItem`, `ClassifyDocumentOutput`, `ExtractDocumentOutput` |
| ADR-034 | OpenAPI snapshot per migration | 0029 snapshot to ship in Batch 3 / implementation commit |

No new ADRs introduced by this spec.

---

**End of Batch 2 (§6–§10).** Batch 3 (§11 Implementation Checklist ·
§12 Acceptance Criteria · §13 Open Questions · §14 Change Log) follows
on review.

**Awaiting Architect review.** Batch 2 review questions for particular
attention:

1. §6.2 — deliberate 403 (not 404) on tenant-prefix mismatch for
   `file_key`. Deviation from the standard cross-tenant 404 rule
   because `file_key` is a self-constructed value not a resource
   lookup. Confirm or revert to 404.
2. §8.3 — legacy direct-file-key bypass (no `documents` row). Keep
   for backward compatibility or require upload-first universally
   post-v1.0?
3. §9.6 — `max_tokens=4096` for `extract_invoice`. Based on estimated
   tail of real invoices (10-20 line items). Tighten or loosen?
4. §10.3 CSP — `'unsafe-inline'` on `style-src` is the pragmatic
   concession. Acceptable for v1.0 or add a nonce-based mechanism now?

