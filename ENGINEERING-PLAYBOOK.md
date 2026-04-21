# Engineering Playbook — ASP (AI Service Platform)

Lessons learned from the PAP (Playwright Automation Platform) project.
Applied to ASP: FastAPI, PostgreSQL, SQLAlchemy async, Alembic, Redis, Celery, Docker.

---

## 1. Project Memory (CLAUDE.md)

### Rule: Update CLAUDE.md on Every Migration
After writing/applying any migration, immediately update:
1. Migration head number
2. Applied chain sequence
3. Any new ADR entries

---

## 2. Database & Migration Conventions

### Migration Files
- **Sequential numeric IDs** — `0001`, `0002`, ..., `0005` (not hex hashes)
- **down_revision** — always verify with `alembic current` before writing
- **Single head** — `alembic heads` must show exactly one head after apply
- **Linear chain** — no branching

### Gate 1: Schema Before ORM
```bash
\d table_name  # Run this BEFORE writing ORM model
```
Map every DB column 1:1 to ORM. Never assume column types from neighbouring columns.

### Gate 2: Type Verification
```sql
SELECT column_name, udt_name FROM information_schema.columns WHERE table_name = 'your_table';
```
- `uuid` → `sa.UUID(as_uuid=True)`
- `varchar` → `sa.String(N)`
- `timestamptz` → `sa.TIMESTAMP(timezone=True)` or `sa.DateTime(timezone=True)`

### Gate 5: Migration Application
```bash
alembic current          # Copy exact string as down_revision
alembic upgrade head     # Apply
alembic heads            # Must show single head
```

### G-PROMPT-REACH: Prompt Template Reachability (added 2026-04-18, ASP-OUT-015)

For every new or modified `prompt_templates` row, verify reachability
by running a probe using the handler's actual `maturity_level` value
(default: `"L2"` for most handlers). The probe must resolve to the
intended row — not raise `PromptNotFoundError` and not resolve to a
stale row.

**Mandatory rules:**

1. **Use `get_prompt_variant()` directly in the probe**, not
   `get_prompt()`. Match the handler's actual resolution path —
   different functions have different fallback semantics.
2. **A migration that deactivates an existing row must confirm a
   reachable replacement exists** at the same or fallback maturity
   level BEFORE the deactivation is committed.
3. **Default maturity of `"L2"` is the most common failure mode.** If
   the handler defaults to `"L2"` and the new row is at `maturity="*"`,
   the fallback chain `(caller, L2) → (caller, *)` must be available
   via the resolution function. If the function is strict-exact (no
   fallback), the row is unreachable for default callers.

**Why this gate exists.** Migration 024 (ASP-FEAT-ASP-03 v2.0) broke
the PAP production path by deactivating the L2 override row while
inserting v4 rows only at `maturity="*"`. `get_prompt_variant` was
strict-exact and had no fallback. Every default-maturity PAP call
failed immediately after the migration applied. Root-caused during
Step 5 unit verification; fixed via ASP-OUT-014 Option A (4-level
fallback chain added to `get_prompt_variant`). This gate exists to
catch the same class of failure at pre-write time rather than
post-apply.

**Example probe shape:**

```python
from app.registry.prompt_registry import get_prompt_variant
from app.registry.prompt_registry import PromptNotFoundError

# Simulate a handler default call
try:
    p = await get_prompt_variant(
        service_type="generation",
        task="generate_test_cases_with_inventory",
        caller_module="playwright_runner",   # real caller
        maturity_level="L2",                  # handler default
        ab_variant="inventory",
    )
    assert p.version == 4, f"expected v4, got v{p.version}"
except PromptNotFoundError:
    raise AssertionError("migration break — no v4 row reachable")
```

Run this probe against the live DB before committing any migration
that touches `prompt_templates`. Pre-write gate result is PASS only
if the probe resolves to the intended row.

**Expanded rule (added 2026-04-21, ASP-OUT-051 — P1 recurrence).**

**G-PROMPT-REACH must be run for ALL expected `caller_module` values,
not just the seeded value.** A prompt row that only resolves for its
seeded caller is unreachable for all other callers. At minimum the
probe matrix must cover:

- The explicitly seeded `caller_module` value (the one the migration
  INSERTs)
- `"playwright_runner"` — canonical PAP caller for generation tasks
  and NLP inferencing from test infrastructure
- `"test_generator"` — canonical PAP caller for F-01-10 interactive
  test-generator panel
- `"*"` catch-all probe — confirm the row is reachable from any
  unexpected caller

**Why this rule exists.** Migrations 026/027 (ASP-FEAT-ASP-02 v1.0
F-03-02 build) seeded prompt rows at `caller_module='test_generator'`
only. The Commit B/C verification ran G-PROMPT-REACH **with
`caller_module='test_generator'` only**, which passed trivially. When
PAP Block 3 invoked the four F-03-02 tasks from
`caller_module='playwright_runner'`, every fallback-chain level
missed → `PromptNotFoundError` → 500 → P1 (ASP-OUT-045). This was
the **same class of regression as ASP-OUT-014** (migration 024), just
at a different point in the fallback chain (caller axis this time,
maturity axis previously).

**The gate failed because it was run with insufficient caller
coverage.** The fix is not a new tool or a new chain level — it is a
procedural tightening of the gate itself. Run multi-caller probes
every time. Do not trust "my migration inserts for caller X, I tested
caller X, that's enough."

**Reference probe runner:** `tests/_reach_probe_f0302.py` (used to
verify migration 0028 reach). Copy-and-adapt pattern for every future
`prompt_templates` migration.

### Known Gotcha: Partial Migration Failures
When a migration fails mid-way:
1. Check `alembic_version` table — it shows the LAST successful revision
2. Check if the table/column was partially created
3. Drop the partial artefact: `DROP TABLE IF EXISTS ... CASCADE`
4. Re-run `docker compose up` to re-apply

### Known Gotcha: UUID vs VARCHAR tenant_id
If your `tenants` table maps `tenant_id` as UUID but the DB column is VARCHAR(64), SQLAlchemy will generate `WHERE tenant_id = $1::UUID` which fails. Fix: use `cast(Model.tenant_id, String) == tenant_id_str` in queries.

---

## 3. Datetime Rules

### NEVER mix naive and aware datetimes
- DB uses `TIMESTAMP WITH TIME ZONE`
- Python always uses `datetime.now(timezone.utc)`
- Never use `datetime.utcnow()` (returns naive)
- Never use `datetime.now()` without timezone

### ORM updated_at Patterns
- **NOT NULL with server_default**: needs BOTH `server_default=func.now()` AND `onupdate=utcnow`
- **NULLABLE**: `onupdate` only
- If `onupdate` is missing from model, set explicitly:
  ```python
  record.updated_at = datetime.now(timezone.utc)
  ```

---

## 4. Authentication & Authorization Patterns

### ASP Auth Flow
1. Client sends `X-Api-Key` header
2. Gateway looks up tenant by bcrypt-hashed key
3. Tenant ID extracted → passed to service layer
4. Cost quota checked before invocation
5. Cost event emitted after successful call

### Cross-Tenant Responses
- Always return **404** (not 403) for cross-tenant access
- Existence must not be leaked across tenants

---

## 5. API Contract Conventions

### Endpoint Prefix
- Gateway: `/api/v1/ai/invoke` (POST), `/api/v1/ai/jobs/{job_id}` (GET)
- All AI service calls routed through the gateway

### Response Wrapper
```json
{ "items": [...], "total": N, "page": 1, "page_size": 20 }
```
For paginated endpoints. Single-item responses use the response model directly.

### File Downloads
Always use JWT Bearer + fetch() + Blob URL. Never `?api_key=` query params.

### File Uploads
Enforce size limit at **endpoint level** (not just Nginx):
1. Check `Content-Length` header before reading body
2. Check `len(file_bytes)` after reading, before processing

### `python-multipart` dependency (added 2026-04-21, ASP-OUT-060)

FastAPI multipart file upload (`File(...)` / `Form(...)` parameters)
requires `python-multipart` in `requirements.txt`. **It is not a
FastAPI transitive dependency — it must be explicitly declared.**
Add it at any point a file upload endpoint is introduced.

Failure mode if missing: FastAPI raises
`RuntimeError: Form data requires "python-multipart" to be installed`
at module import time — the router never registers, and the
application fails to start cleanly. Surfaced during I-DOC-05
implementation (ASP-FEAT-ASP-04 v1.0 upload endpoint).

Governed pin: `python-multipart==0.0.9`. Upgrade only with an
explicit compatibility test against the FastAPI + Starlette versions
in `requirements.txt` — the multipart parser is closely coupled to
the ASGI layer.

---

## 6. Audit Trail Pattern

### Structure
```sql
INSERT INTO audit_log (tenant_id, entity_type, entity_id, action,
  changed_by, changed_at, diff_json)
```

### Rules
- `entity_type` must be in any CHECK constraint — verify before first audit write
- `diff_json` for password operations: `{password_reset: true}` — NEVER include the hash
- Audit write + data change in SAME transaction — rollback both on failure

---

## 7. Spec Review Methodology

### Categories
| Level | Meaning | Action |
|-------|---------|--------|
| **Critical** | Blocks implementation. DB will reject, runtime crash, security hole | Must fix before implementation |
| **Design** | Spec is imprecise or inconsistent but not broken | Recommend TSCD |
| **Minor** | Cosmetic, naming, documentation lag | Note for awareness |

### Always Check
1. **CHECK constraints** — does the DB permit the values the spec uses?
2. **FK targets** — does the referenced column actually exist? Run `\d table_name`
3. **Auth flow e2e** — who can call this? What tenant? What happens cross-tenant?
4. **Timezone awareness** — does the spec say TIMESTAMPTZ? Does the ORM use timezone=True?
5. **Migration numbering** — sequential? Correct down_revision?

---

## 8. Implementation Workflow

### Sequence
1. **Read spec fully** before writing any code
2. **Check all DB constraints** against live database
3. **Write migration** (if needed) — apply first
4. **Write ORM model** — map every column 1:1
5. **Write Pydantic schemas** — request + response
6. **Write service layer** — business logic
7. **Write API router** — register in main.py
8. **Update docs** — ASP-INDEX.md + ASP-SCHEMA-CURRENT.md (canonical, in-place)
9. **Build + test** — Gate 7 checks + full AC verification

### Gate 7 Checks (Before Every Commit)
```bash
# Backend import check
python -c "from app.services.{module} import {function}; print('OK')"
python -c "from app.gateway.router import router; print('OK')"
```

### AC Verification Rules
- **100% AC passage required** — no partial completions
- Test every AC, not just the happy path
- Security ACs (cross-tenant, auth) are non-skippable
- Mark COMPLETE only after ALL ACs pass

---

## 9. Docker Conventions

### Rebuild After Code Changes
```bash
docker compose up -d --build ai-service  # Always --build after code changes
```
`docker compose restart` uses the cached image — your changes won't be picked up.

### Services
| Service | Port | Purpose |
|---------|------|---------|
| ai-service | 8000 | FastAPI app |
| celery-worker | — | Async task processing |
| flower | 5555 | Celery monitoring |
| postgres | 5434 | PostgreSQL 16 |
| redis | 6379 | Cache + message broker |
| minio | 9000/9001 | S3-compatible storage |

### Migration on Startup
Alembic runs `upgrade head` during container startup. If migration fails: check logs, fix DB state, rebuild.

---

## 10. Document Management

### Canonical Files (Edit In-Place)
```
ASP-INDEX.md              — Updated on every migration + feature status change
ASP-SCHEMA-CURRENT.md     — Updated on every migration application
ASP-ADR.md                — Updated when new architectural decisions are locked
CLAUDE.md                 — Updated on every migration (head + chain)
```

### Never Version These Files
No `ASP-INDEX-v1_37.md`. Single file, updated in-place.

### Governance Doc Sync Targets (ADR-026.2 — CANONICAL LIST)
All living governance documents must be synced to ALL targets in the same operation.
A "synced" claim requires every target verified identical (diff).
Add new targets to this list BEFORE the first sync to them.

```
1. C:\Users\amodp\projects\asp\                          (repo — authoritative)
2. C:\Users\amodp\projects\asp-projects\00-index\        (working copy — primary)
3. C:\Users\amodp\projects\asp-projects\00-index\communication\  (working copy — Chief Architect review)
```

Documents covered: ASP-INDEX.md, ASP-SCHEMA-CURRENT.md, ASP-ADR.md, ASP-DEFECT-REGISTER.md

---

## 11. Common Mistakes & Fixes

| Mistake | Fix |
|---------|-----|
| Marking feature COMPLETE with untested ACs | Test ALL ACs before COMPLETE. 100% required. |
| Using `datetime.utcnow()` | Use `datetime.now(timezone.utc)` |
| Sorting by UUID for chronological order | UUIDs are random. Sort by `created_at` |
| Skipping `\d table_name` before ORM | Always verify column types against live DB |
| `docker compose restart` after code changes | Use `docker compose up -d --build` |
| Assuming another team implements tasks | All tasks are your responsibility regardless of label |
| Editing versioned doc files instead of canonical | Only edit `ASP-INDEX.md`, not versioned copies |
| Deferring doc updates to "later" | Post-implementation checklist is part of the implementation |
| Prompt templates only in running DB, not committed | All prompts via committed Alembic migrations. Running DB is not source of truth. (ADR-027) |
| Pre-writing migrations for unimplemented tasks | Migrations describe executed reality, never planned work. (ADR-028) |
| Merging without fresh-DB alembic test | `alembic upgrade head` on empty DB must pass before any PR merges. (ADR-029) |
| Branch merges creating duplicate revision numbers | Blocking defect. Single head convention is non-negotiable. |
| Assuming task exists from spec alone | Verify task exists via code or `GET /capabilities` before calling. (ADR-030) |
| Not auditing cost_events vs VALID_TASKS | Periodic audit catches drift early. Cross-reference quarterly. |
| Claiming "synced" without verifying BOTH locations | After every deployment, verify both repo and working copy reflect the change before claiming sync. (ADR-026.1) |

---

## 12. Celery & Async Patterns (ASP-Specific)

### Async Services
Doc Intelligence (ASP-04) and Prediction (ASP-05) use Celery for long-running tasks:
- Gateway returns `JobAcceptedResponse` with `job_id` immediately
- Client polls `GET /api/v1/ai/jobs/{job_id}` for result
- Job status stored in `async_jobs` table

### Cost Aggregator
- Runs via Celery beat schedule
- Monthly rollup is idempotent — safe to re-run
- Writes to `cost_monthly_reports` table

### Webhook Delivery
- Exponential backoff on failure
- HMAC-SHA256 signing for payload integrity
- Configured per-tenant in `webhook_registrations` table

### Asyncpg Loop Affinity in Celery Beat Tasks (ASP-DEFECT-022)

asyncpg connections carry event loop affinity. Never reuse a connection pool
across `asyncio.run()` calls in Celery tasks — each task invocation creates
a new event loop. Use per-invocation `create_async_engine()` +
`engine.dispose()` for beat tasks with monthly or infrequent schedules. The
overhead is acceptable when the task fires rarely.

Symptom when violated: first invocation succeeds; second invocation fails
with `got Future <Future pending> attached to a different loop` because the
pool created against loop A is reused from loop B. See
`app/cost/aggregator.py` for the governed pattern.

### Celery Task DB-Write Rule (added 2026-04-21, ASP-OUT-064)

**Every Celery task body that calls `asyncio.run(...)` must use
per-invocation `create_async_engine` + `engine.dispose()` for every DB
touch. Do not call `app.infra.db.get_session()`,
`app.cost.meter.emit_cost_event`, or any other shared-pool helper from
inside `asyncio.run()` bodies. Reference implementations:
`app/cost/aggregator.py::_do_aggregation`,
`app/services/doc_intelligence.py::_async_*`.**

Governed precedent (four instances of this class of bug to date):

- **ASP-DEFECT-022** (2026-04-18, ASP-10 cost aggregator) — first
  instance; set the playbook.
- **ASP-DEFECT-024** (2026-04-21, ASP-04 Doc Intelligence, three sites
  in `doc_intelligence.py`) — same class; first ASP-04 remediation.
- **ASP-FEAT-ASP-04 v1.0 I-DOC-11 in-cycle extension** — caught
  `_async_emit_cost` going through the shared-pool helper during AC
  suite bring-up; fixed in same commit.
- **ASP-DEFECT-025** (2026-04-21, ASP-05 Prediction,
  `app/services/prediction.py`) — fourth instance; surfaced by the
  ASP-OUT-063 loop-affinity platform audit; RESOLVED in the same
  ASP-OUT-064 turn via the playbook.

**The helper `app.cost.meter.emit_cost_event` is safe from FastAPI
request handlers (consistent event loop, shared pool correct) but is
UNSAFE from inside `asyncio.run()` in Celery task bodies (new loop
per invocation collides with the shared pool).** Celery tasks that
need to emit cost events MUST use a per-invocation engine + direct
`INSERT INTO cost_events` SQL. Reference implementations:
`app/services/doc_intelligence.py::_async_emit_cost` and
`app/services/prediction.py::_async_emit_cost`.

### Pre-Spec Survey Mandatory Check (added 2026-04-21, ASP-OUT-064)

Every pre-spec survey for an ungoverned service must include this
mandatory check:

> **Search for `create_engine()` and `asyncio.run()` in Celery task
> bodies. Any hit is presumed CRITICAL until verified fixed.**

Surfaced grep pattern:

```
grep -rn "create_engine\|asyncio.run\|get_session\|emit_cost" \
    app/services/<svc>/ app/api/<svc>.py
```

Every hit must be triaged via the ASP-OUT-063 audit-finding risk
schema (CRITICAL / HIGH / MEDIUM / LOW) before the spec's gap matrix
is finalised. If a CRITICAL finding surfaces, it must be filed as a
new defect (same severity + disposition as ASP-DEFECT-024 /
ASP-DEFECT-025) and scheduled as the S-1 gate of the spec cycle —
before any other implementation item ships.

Audit artefacts: `docs/audits/` (governed). Reference:
`docs/audits/loop-affinity-audit-2026-04-21.md`.
