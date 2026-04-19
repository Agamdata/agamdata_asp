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
