# ASP-FEAT-ASP-04 + ASP-13 Pre-Spec Survey (Doc Intelligence Demo)

**MSG-ID:** DEV-IN-041
**Authored:** 2026-04-21
**Directive:** ASP-OUT-041
**Scope:** Joint governance of ASP-04 (Doc Intelligence) + ASP-13
(Dashboard Intelligence, Doc Intelligence panel).

This survey is the input for Batch 1 spec authoring. **No spec writing
until this survey is reviewed.** Current migration head: **0027**. Next
available migration: **0028**.

---

## 1. Survey 1 — ASP-04 Doc Intelligence

### 1.1 File inventory

| File | Path | LOC | Purpose |
|---|---|---:|---|
| `doc_intelligence.py` | `app/services/doc_intelligence.py` | 267 | Handler + Celery task + sync cost/status helpers |
| `storage.py` | `app/infra/storage.py` | ~40 | boto3 S3/MinIO singleton (`download`, `upload`) |
| `async_jobs` table | `app/models/db_models.py:158-180` | — | Job state (job_id, tenant_id, service_type, task, status, result_json, webhook_*) |
| `router.py` jobs endpoint | `app/gateway/router.py:170` | — | `GET /api/v1/ai/jobs/{job_id}` — tenant-scoped status lookup |
| Existing prompts | `alembic/versions/0002_seed_prompt_templates.py:234-256` | — | `extract_document` + `classify_document` rows at (`*`, `*`) |
| Async service registration | `app/gateway/router.py:62` | — | `ASYNC_SERVICES = {"doc_intelligence", "prediction"}` |
| Celery beat/worker | `app/worker.py`, `docker-compose.yml` | — | `-B` flag + volume mount already governed (I-RAG-04) |

No dedicated `app/schemas/doc_intelligence_schemas.py` exists — output
schemas live inline in `doc_intelligence.py`.

### 1.2 Current task registrations

**Actual repo state:**

```python
# app/services/doc_intelligence.py:30
VALID_TASKS = {"extract_document", "classify_document"}
```

**Directive expected:** `extract_invoice, classify_document, extract_fields`.

**Gap:** directive names diverge from implementation. Current scheme is
two generic tasks (`extract_document` + `classify_document`) rather
than invoice-specific names. Decision required for §2 of the spec:

- **Option A** — Keep generic tasks; let caller supply `doc_type` hint
  at classify time; prompts differentiate behaviour. (Minimal change;
  preserves existing contract.)
- **Option B** — Add three new tasks per directive (`extract_invoice`,
  `extract_fields` + existing `classify_document`). Deprecate
  `extract_document`. (Richer surface; matches directive verbatim but
  churns existing prompts + callers.)
- **Option C** — Keep `extract_document` + `classify_document`; add a
  new `extract_invoice` as an invoice-specialised variant. (Additive;
  preserves backwards compat; directive's `extract_fields` is an alias
  for the generic path.)

**Recommendation: Option C** — additive, Type B, matches existing
governance posture. Demo invoice-flow is unblocked; generic tasks
remain available for future doc types.

### 1.3 S3/MinIO integration

- **Endpoint.** `settings.S3_ENDPOINT` (default `http://localhost:9000`).
  Production values from env.
- **Bucket.** `settings.S3_BUCKET_DOCS` (default `asp-documents`).
  Single shared bucket; tenant isolation by key prefix (ADR-013).
- **Helpers.** `app.infra.storage.download(file_key)` + `upload(...)`.
  Neither is exposed over HTTP today — S3/MinIO is an internal surface.
- **Tenant prefix enforcement.** `doc_intelligence.handle()` lines
  62-65 hard-check `file_key.startswith(f"{tenant_id}/")` before
  enqueueing — ADR-013 compliant.
- **Client.** `boto3` with `signature_version="s3v4"` (compatible with
  MinIO). Driver in `requirements.txt` ✓.

**Gap G-04-01.** No upload endpoint exists. The demo flow's Step 1
(engineer uploads PDF) needs a Gateway endpoint that takes multipart
file + returns the `file_key`. New endpoint required. Scope decision:

- **Option A** — dedicated `POST /api/v1/ai/documents` multipart
  endpoint that writes to S3 under the authenticated tenant's prefix
  and returns `{"file_key": "...", "size_bytes": N}`.
- **Option B** — pre-signed PUT URL flow: client requests a URL, PUTs
  directly to MinIO, then invokes ASP-04 tasks by `file_key`. Scales
  better; no file body ever transits the Gateway.

**Recommendation: Option A for v1.0 pilot** — smaller surface, no
CORS/endpoint-exposure questions at MinIO. Revisit B at Atrium scale.

### 1.4 Async pattern

- **Entry.** `handle()` in `doc_intelligence.py`:
  1. Validates `file_key` tenant prefix.
  2. Creates `async_jobs` row with `status='queued'` and any
     `webhook_url`.
  3. Dispatches `asp.doc_intelligence` Celery task via
     `celery_app.send_task`.
  4. Returns `JobAcceptedResponse(request_id, job_id, status='queued')`.
- **Worker.** `process_document` (`@celery_app.task(bind=True,
  max_retries=3)`):
  1. Transitions status → `running`.
  2. `storage.download(file_key)` → bytes.
  3. `_extract_text()` via pdfminer (PDF) or python-docx (DOCX).
  4. Fetches prompt row; calls `anthropic.Anthropic.messages.create`
     SYNCHRONOUSLY (not async — `anthropic.Anthropic`, not
     `AsyncAnthropic`).
  5. Parses output, updates job → `completed`, emits cost event, fires
     webhook (wraps `asyncio.run(_fire_webhook_async(...))`).
  6. On exception: status → `failed`, `self.retry(countdown=60)`.
- **Client polling.** `GET /api/v1/ai/jobs/{job_id}` — tenant-scoped
  row lookup (ADR-012 / ADR-022 Zone 1 leak-safe 404).

### 1.5 Current output schemas (inline, not `app/schemas/`)

```python
# app/services/doc_intelligence.py:35-51
class ExtractDocumentOutput(BaseModel):
    fields: dict
    tables: list[dict]
    confidence: float
    page_count: int

class ClassifyDocumentOutput(BaseModel):
    doc_type: str
    confidence: float
    suggested_fields: list[str]
```

**Gap G-04-02.** Schemas lack `ConfigDict(extra=...)` — implicit
permissiveness. Also missing from `app/api/capabilities.py`
`TASK_SCHEMA_MODELS` registry → `GET /api/v1/ai/schemas/{service}/{task}`
returns 422 for either task today. Violates ADR-030.

**Gap G-04-03.** `ExtractDocumentOutput.fields: dict` is untyped. For
the demo invoice flow we need a governed invoice-field shape (vendor,
invoice_number, date, line_items, total_amount, tax_amount, currency).
Likely a distinct `ExtractInvoiceOutput` model for Option C (§1.2).

### 1.6 ADR compliance gaps

| ADR | Area | Status | Note |
|---|---|---|---|
| **ADR-006** Cost Meter never raises | `_sync_emit_cost()` via `asyncio.run` | ⚠️ **GAP G-04-04** | Not wrapped in try/except. A cost-meter failure (Redis down, DB timeout) propagates out of the Celery task and triggers a retry. Same pattern as DEFECT-020 resolution for the Gateway. |
| **ADR-012** Tenant isolation | `tenant_id` required for S3 + job row | ✅ | Hard-enforced at handle entry (line 63-65) and job row (line 71). |
| **ADR-013** S3 tenant prefix | `file_key.startswith(f"{tenant_id}/")` | ✅ | Compliant. |
| **ADR-009** TIMESTAMPTZ everywhere | `async_jobs.created_at/completed_at` | ✅ | Both TZ-aware. |
| **ADR-010** structlog | `doc_intelligence_queued` emitted | ⚠️ **GAP G-04-05** | Celery task path emits nothing at `running`/`completed`/`failed` transitions. Only `doc_intelligence_queued` from the enqueue side. Observability gap; operators can't trace via logs. |
| **ADR-028** Migrations = reality | `0002_seed_prompt_templates` has rows | ✅ | Existing rows tracked. |
| **ADR-030** Capabilities surface | Service listed in `SERVICE_CAPABILITIES` | ⚠️ **GAP G-04-02 bis** | Listed in `services` dict but `TASK_SCHEMA_MODELS` empty for doc_intelligence → schemas endpoint broken. |

**Gap G-04-06 (CRITICAL — latent, same class as DEFECT-022).** Lines
136-144, 208-214: `doc_intelligence.py` uses
`sqlalchemy.create_engine(sync_url)` after regex-stripping `+asyncpg`
— this imports `psycopg2` which **is NOT in requirements.txt**
(verified: only `asyncpg==0.29.0` is listed). The sync helpers
`_sync_update_job_status` and `_sync_emit_cost` + the inline
prompt-row fetch all share the same failure mode.

**This is exactly the DEFECT-022 class of bug.** Either dormant
(because the doc_intelligence Celery task hasn't been exercised in
pilot) or actively broken the moment any doc_intelligence task runs.
Must be fixed before §1.4 async flow becomes production-grade.

**Remediation options:**
- **Option A** — Port to `asyncio.run(async_fn)` + per-invocation
  `create_async_engine` (the governed pattern from DEFECT-022
  resolution; loop-affinity lesson is already in
  `ENGINEERING-PLAYBOOK.md` §12).
- **Option B** — Add `psycopg2-binary` to `requirements.txt`. Two
  Postgres drivers in the image; discouraged by the Atrium single-
  driver posture.

**Recommendation: Option A** — consistent with DEFECT-022 resolution;
no new requirements line; governed pattern already in the playbook.

### 1.7 Existing prompt rows

```
service_type='doc_intelligence'
  extract_document   | caller_module=*  | maturity_level=* | v1 | active
  classify_document  | caller_module=*  | maturity_level=* | v1 | active
```

Both seeded in migration `0002`. System prompts are generic
"logistics document" text — suitable for a general-purpose extractor
but **not invoice-specific**.

**Gap G-04-07.** v1.0 spec scope needs an invoice-tuned system prompt.
If Option C in §1.2 is accepted, migration 0028 seeds:
- `extract_invoice` (generation or doc_intelligence — decision
  required; directive implies doc_intelligence scope).
- Optionally v2 of `classify_document` with invoice-aware prompt.

### 1.8 Pre-write gate

| Gate | Status | Notes |
|---|---|---|
| **G-1 Schema** | Pending decision | No new Postgres table if Option C (§1.2); `async_jobs` already supports the flow. If a `documents` registry table is added (audit trail of uploads per tenant), DDL migration required. |
| **G-2 Types** | Pending decision | Depends on G-1. |
| **G-3 Contract** | **OPEN** | Invoice field shape (§1.5 G-04-03) + upload endpoint contract (§1.3 G-04-01) both need §6/§7 definition. |
| **G-4 Audit (CHECK)** | N/A unless new table |
| **G-5 Migration** | Next free: **0028** (prompt-only if Option C), **0029** if DDL added |
| **G-6 Frontend** | **OPEN — see Survey 2** |
| **G-7 Dependency** | New modules likely: `app/schemas/doc_intelligence_schemas.py`; possibly `app/api/documents.py` for upload endpoint. Import-check in Commit A. |
| **G-8 Prompt Reach** | **OPEN** | If new prompt rows added, reach check at (`test_generator`|caller, `*`) fallback level. |

---

## 2. Survey 2 — ASP-13 Dashboard Intelligence

### 2.1 File inventory

| File | Path | LOC | Purpose |
|---|---|---:|---|
| `dashboard.py` | `app/services/dashboard.py` | 122 | Handler — structured + screenshot modes |
| Existing prompts | `prompt_templates` rows | — | 4 tasks at (`*`, `*`) |
| Router registration | `app/gateway/router.py:58` | — | `"dashboard_intelligence": dashboard.handle` |

### 2.2 Current capability

Four **existing** tasks on `dashboard_intelligence`:

- `interpret_chart` — structured or screenshot.
- `narrate_dashboard` — structured or screenshot.
- `detect_anomaly` — structured only.
- `suggest_drilldown` — structured only.

All four share a single output schema `DashboardOutput` (`insight`,
`anomalies`, `suggested_actions`, `confidence`). No doc-panel or
PDF-review capability exists today.

### 2.3 Frontend assets

**No frontend exists.** Filesystem scan of repo roots confirms:

- No `frontend/`, `ui/`, `web/`, `dashboard-ui/`, `static/`, or
  `templates/` directory.
- No build tooling (`package.json`, `vite.config.*`, `next.config.*`)
  at repo root.
- `docker-compose.yml` has no frontend service.

ASP is a headless FastAPI backend today. Every ASP-13 call is consumed
by upstream clients (LogiCRM, PAP test-generator panel). The product
demo dashboard panel will be the **first frontend asset owned by this
repo**. This is a major scope decision for the spec cycle.

**Gap G-13-01 (CRITICAL scope question).** Where does the dashboard UI
live?

- **Option A** — New top-level `frontend/` directory in this repo.
  Served either as static files by FastAPI (for pilot) or built and
  deployed separately. Adds a build step to Docker tooling.
- **Option B** — Dashboard is a separate repo. ASP ships API only;
  demo frontend is downstream.
- **Option C** — Dashboard UI is part of an already-existing
  LogiCRM / PAP repo and consumes ASP as an external service.
- **Option D** — Server-rendered HTMX/Jinja2 pages served by FastAPI
  directly — no build step, no JS framework.

**Recommendation: Option D for pilot demo.** Quickest path to a live
invoice-review panel. Server-rendered Jinja2 + HTMX for reactive
updates (file upload, polling) and `pdf.js` via CDN for the viewer.
Zero build tooling; zero new Docker service. Revisit at Atrium (likely
Option A or B there).

### 2.4 Current API surface for ASP-13

Exposed only through the Gateway:

- `POST /api/v1/ai/invoke` with `service_type="dashboard_intelligence"`
  and one of the four tasks above.

No ASP-13-specific endpoints. No static-file endpoint. No websocket or
SSE surface.

### 2.5 How ASP-13 receives data

Caller supplies data in the invocation payload:

- Structured mode: `payload.chart_context` + `payload.dashboard_context`
  are arbitrary JSON blobs. LLM interprets.
- Screenshot mode: `payload.image_data` (base64) + `payload.image_mime`.
  Anthropic vision path.

ASP-13 does not pull from any data warehouse, BI tool, or
`cost_monthly_reports` table directly. All inputs are caller-provided.
This fits the Zone 2 Shared Contract model.

### 2.6 Gaps for the Doc Intelligence panel

**Need to build from scratch:**

| Component | Status | Scope |
|---|---|---|
| PDF viewer | **MISSING** | Inline PDF rendering in browser. |
| File upload component | **MISSING** | Multipart POST to the new upload endpoint (G-04-01). |
| Structured data display | **MISSING** | Two-panel layout; confidence-indicator badges per field. |
| Polling loop | **MISSING** | Poll `GET /api/v1/ai/jobs/{job_id}` until `status=completed`. |
| Authentication | **PARTIAL** | Gateway already requires `X-ASP-API-Key`; UI needs a flow for the engineer to acquire/store one. |

**Recommendation stack (per Option D in §2.3):**

- **FastAPI Jinja2Templates** — already supported by FastAPI core; no
  new dependency.
- **HTMX** — included via `<script>` CDN tag; no build step.
- **pdf.js** — included via `<script>` CDN tag for PDF rendering.
- Static CSS — plain CSS; `app/static/` directory.
- Optional: `htmx-sse` extension for job-status streaming (otherwise
  polling).

This stack delivers the demo in ~4-6 net-new files (a few templates +
a small `app/api/dashboard_ui.py` router + CSS + one Jinja partial for
each panel).

---

## 3. Demo Flow — governance mapping

| Step | Current state | Gap count | Spec §§ to author |
|---|---|---:|---|
| 1. Upload invoice PDF | No endpoint; no UI | 2 (G-04-01, G-13-01) | §6 API contract + §7 request shape + §10 security |
| 2. Classify | Task exists; UI missing | 1 (G-13-01) | §6 (no API change) + §11 UI |
| 3. Extract | Task exists; invoice-specific schema missing; latent psycopg2 bug | 3 (G-04-03, G-04-06, G-04-07) | §5 data model + §6 + §9 prompt |
| 4. Review panel | Nothing exists | 1 (G-13-01 implementation detail) | §11 UI + §12 AC block |

---

## 4. Pre-write gate summary

| Gate | Outcome |
|---|---|
| Migration number | **0028** is free (`alembic heads` → `0027 (head)`; no branching). |
| Chain integrity | Single head `0027` confirmed live + on-disk. |
| Services called | S3/MinIO (`app.infra.storage`), LLM (Anthropic), Cost Meter (`app.cost.meter.emit_cost_event`), webhook service (`app.webhook.service.fire_webhook`), prompt registry (`app.registry.prompt_registry`). |
| New tables | **TBD in §5** — pending Option A/B/C on `documents` audit registry. At minimum: prompt rows (migration 0028); possibly a `documents` table (migration 0029) for tenant-scoped file metadata + upload audit. |
| ADRs governing | ADR-001 (Zone 1 classification), ADR-006 (cost meter), ADR-010 (structlog), ADR-012 (tenant isolation), ADR-013 (S3 prefix), ADR-022 (zone-boundary), ADR-028 (migrations = reality), ADR-030 (capabilities surface), ADR-033 (payload extra-ignore). New ADR candidates: ADR for upload-endpoint contract; ADR for frontend scope. |

---

## 5. Consolidated gap matrix

| Gap | Description | Severity | Surface | Proposed fix |
|---|---|---|---|---|
| **G-04-01** | No upload endpoint for multipart PDF → S3 | HIGH | ASP-04 | New `POST /api/v1/ai/documents` (Option A); S3 key `{tenant_id}/{uuid}.pdf`; returns `{file_key, size_bytes}` |
| **G-04-02** | `doc_intelligence` tasks absent from `TASK_SCHEMA_MODELS` → schemas endpoint broken (ADR-030 gap) | MEDIUM | ASP-04 | Register `ExtractDocumentOutput`, `ClassifyDocumentOutput`, new `ExtractInvoiceOutput` models; expose via `GET /api/v1/ai/schemas/{service}/{task}` |
| **G-04-03** | `ExtractDocumentOutput.fields: dict` untyped; invoice demo needs governed shape | MEDIUM | ASP-04 | New `app/schemas/doc_intelligence_schemas.py` with `ExtractInvoiceOutput` (vendor, invoice_number, date, line_items, total_amount, tax_amount, currency) |
| **G-04-04** | `_sync_emit_cost` not wrapped in try/except — ADR-006 violation (same class as DEFECT-020) | MEDIUM | ASP-04 | try/except around the cost-meter call; log+swallow |
| **G-04-05** | Celery worker path emits no `running`/`completed`/`failed` structlog events | LOW | ASP-04 | Add three structlog events mirroring rag.py pattern |
| **G-04-06** | **CRITICAL — psycopg2 import class-of-bug (same as DEFECT-022)** in `_sync_update_job_status` and `_sync_emit_cost` and inline prompt fetch | **HIGH** | ASP-04 | Port to `asyncio.run` + per-invocation `create_async_engine` per playbook §12 loop-affinity rule |
| **G-04-07** | No invoice-specific prompt row; generic `extract_document` prompt is logistics-tuned | MEDIUM | ASP-04 | Migration 0028 — seed `extract_invoice` prompt row + optionally v2 of `classify_document` with invoice awareness |
| **G-13-01** | **CRITICAL scope question — dashboard UI for the demo does not exist anywhere in the repo** | **HIGH** | ASP-13 | Architect ruling required (Option A/B/C/D in §2.3); recommendation Option D (Jinja2 + HTMX + pdf.js, no build) |
| **G-13-02** | No file-upload UI component | HIGH | ASP-13 | Multipart form + HTMX swap on success; depends on G-04-01 + G-13-01 |
| **G-13-03** | No PDF viewer component | HIGH | ASP-13 | pdf.js CDN + `<canvas>` render pipeline |
| **G-13-04** | No structured-field review panel | HIGH | ASP-13 | Jinja partial; confidence-badge component; copy-to-clipboard |
| **G-13-05** | No polling loop for async job status | MEDIUM | ASP-13 | HTMX `hx-trigger="every 2s"` against `/api/v1/ai/jobs/{job_id}` |

---

## 6. Confirmed decisions needed for §§1–§5 authoring

Surfaced here so the Architect can confirm once and the Batch 1 spec
writes without blocking:

| # | Question | Recommended path | Pending Architect |
|---|---|---|---|
| Q-1 | Task surface (§1.2): add `extract_invoice` additively vs rename generic tasks | **Option C — additive `extract_invoice` + retain `extract_document`/`classify_document`** | ✓ |
| Q-2 | Upload endpoint design (§1.3 / G-04-01) | **Option A — `POST /api/v1/ai/documents` multipart** | ✓ |
| Q-3 | `documents` audit-registry table (§4) | **Not in v1.0** — defer to v1.1. `async_jobs` is sufficient for the demo flow; per-file audit is a separate feature. | ✓ |
| Q-4 | psycopg2 remediation (G-04-06) | **Option A — asyncio.run + per-invocation async engine** (DEFECT-022 playbook pattern) | ✓ |
| Q-5 | Frontend scope (G-13-01) | **Option D — Jinja2 + HTMX + pdf.js, server-rendered, zero build** | ✓ |
| Q-6 | Invoice field shape (G-04-03) | Directive-listed fields (`vendor`, `invoice_number`, `date`, `line_items`, `total_amount`, `tax_amount`, `currency`) as a governed `ExtractInvoiceOutput` with `ConfigDict(extra="ignore")` and `confidence` per field. | ✓ |

---

## 7. Stream plan (post-survey acceptance)

Consistent with prior governance cycles:

- **Stream A** — ASP-04 backend (upload endpoint, psycopg2 remediation,
  Pydantic schemas, invoice prompt, cost-meter wrapping, structlog
  events, AC suite).
- **Stream B** — ASP-13 frontend (Jinja2 templates + HTMX + pdf.js +
  static CSS + ui router + AC suite).
- **Stream C** — Joint governance sync (INDEX, SCHEMA-CURRENT, COMMS-
  LOG, ADR for upload + ADR for frontend scope, ASP-NOTE-013 closure).

---

## 8. Awaiting

Architect review of this survey. No spec writing begins until Q-1
through Q-6 are confirmed (or replaced with alternative rulings) and
the survey is accepted. This file is the governed input for Batch 1.
