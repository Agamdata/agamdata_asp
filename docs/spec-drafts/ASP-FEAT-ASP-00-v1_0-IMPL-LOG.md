# ASP-FEAT-ASP-00 v1.0 — Implementation Log

Chronological record of spec-narrative corrections, implementation rulings, and
phase-gate decisions made during implementation of ASP-FEAT-ASP-00 v1.0.
Entries are appended only. This log will be consolidated into the final
AC-VERIFICATION report at GOVERNED declaration.

---

## 2026-04-17 · Phase 1 — spec narrative correction (49-char key length)

**Context.** §10 "Key format and generation" S-1 bullet and §11 I-03 bullet
previously stated the new API key format is 50 characters. The canonical
regex `^asp_[a-z0-9]{12}_[A-Za-z0-9]{32}$` describes a 49-character string
(3-char scheme + `_` + 12-char prefix + `_` + 32-char secret = 49). Unit test
for I-03 caught the inconsistency when `assert len(raw_key) == 50` failed.

**Ruling (Chief Architect, Option A, 2026-04-17).** Regex is the governed
surface; correct the prose, not the code. Two occurrences of "50" replaced
with "49" in `docs/spec-drafts/ASP-FEAT-ASP-00-v1_0.md`. No code change.
No AC change. The .docx will be re-rendered before GOVERNED declaration.

**Status.** CLOSED.

## 2026-04-17 · Phase 1 — pre-auth `request_id=null` is expected behaviour

**Context.** RFC 7807 envelope includes `request_id` on every error response.
The Gateway router allocates `request_id` **after** auth succeeds; a 401 on
an invalid or missing API key therefore has no correlation ID available in
`request.state`.

**Ruling (Chief Architect, 2026-04-17).** This is expected and correct.
Pre-auth errors legitimately emit `request_id: null`. Post-auth errors (any
path where the router set `request.state.request_id`) emit the correlation
ID matching the `X-Request-Id` response header. AC-S5-05 verifies the null
case; AC-S5-04 verifies the populated case.

**Status.** CLOSED — noted in §11 I-RFC7807 handler docstring. No spec text
change required; the behaviour is already captured in AC-S5-05.

## 2026-04-17 · Phase 1 — test isolation note

**Context.** First-pass unit test for the RFC 7807 handler reused a shared
`scope` dict across successive `Request(scope)` constructions. Starlette's
`Request.state` mutates `scope['state']` by reference, so a second Request
from a shallow-copied scope saw the first Request's `request_id`. The test
incorrectly failed the pre-auth-null assertion.

**Resolution.** Fixed the test to construct a fresh `scope` dict per Request.
Production code unaffected — each real HTTP request has its own ASGI scope.

**Status.** CLOSED — test-only bug.

## 2026-04-17 · Phase 2 pre-migration — legacy-prefix match approach for I-04

**Context.** The legacy backfill uses `'leg_' || substr(id::text, 1, 8)` as the
`key_prefix` value on backfilled rows. The spec draft §10 auth.py snippet
used `TenantApiKey.key_prefix.like("legacy%")` because the earlier backfill
prefix was `'legacy' || substr(...)`. After the Architect's prefix change
to `'leg_<hex8>'`, a naive `.like("leg_%")` would be incorrect: `_` is a
SQL LIKE single-char wildcard, so the pattern matches any 12-char prefix
starting `leg` + one arbitrary char — including valid new-format prefixes
like `legabc123def`.

**Ruling (Chief Architect, 2026-04-17).** Use
`func.left(TenantApiKey.key_prefix, 4) == "leg_"` in I-04. Deterministic,
no LIKE wildcard escaping, explicit. Locked as the I-04 implementation
approach; no separate ruling required when Phase 3 begins.

**Status.** OPEN — will close when I-04 ships in Phase 3.

## 2026-04-17 · Phase 2 pre-migration verification

**Live DB state at Phase 2 entry.**

- `alembic current`: **`0022 (head)`**
- `tenants.api_key_hash`: present, `VARCHAR(255) NOT NULL`
- Active tenants with hash: **1** (`pap_runner`, id `daa3f639-8cac-4136-b8ab-5ea336be5233`)
- Backfill will produce one `tenant_api_keys` row with
  `key_prefix = 'leg_daa3f639'` (12 chars, fits VARCHAR(12)).

**Status.** Informational; Phase 2 green-lit to proceed.

## 2026-04-17 · v2.0 forward-note — `form_data` amendment (migration 024, NOT 023)

**Context.** Chief Architect accepted PAP's `form_data` request into
PAP-ASP-REQ-ASP-03 v2.0 as Type B additive. Consumer-isolated (ADR-033
`extra="ignore"` covers PAP's immediate usage). Response schema unchanged.
No cross-consumer review required.

**Ruling (Chief Architect, 2026-04-17).** form_data lands with migration 024
(coverage-aware generation), not 023. Amendment scope:

- Schema: add `form_data: dict[str, str] | None = None` to
  `GenerateTestCasesWithInventoryPayload`.
- Handler renders into the v4 prompt as a new section:

      --- Form Data Context ---
      {form_data}

  When absent/null: render `"No form data provided — generate realistic test
  values from field names and context."`
  When present: render the dict via `str(payload.form_data)`.
- Two ACs added to v2.0 suite:
  - **AC-FORM-01** — call with `form_data={"first_name": "Alice", "email":
    "alice@example.com"}` yields at least one step whose `value` contains
    `"Alice"` or `"alice@example.com"`.
  - **AC-FORM-02** — call without `form_data` → 200, no 422, behaviour
    unchanged from v1.1.
- Amendment log entry: add **C-15** to PAP-ASP-REQ-ASP-03 v2.0 change table
  before formal acceptance (PAP-side document).

**Status.** DEFERRED to migration 024. No action in Phase 2. Tracked here so
it is not lost when Phase 6 begins on PAP confirmations for Q-1 / Q-2.

## 2026-04-17 · Phase 2 I-01 — migration 023 applied; fresh-DB test passed after ASP-DEFECT-021 fix

**Tooling gap.** The ADR-029 fresh-DB upgrade gate initially appeared to run
against `aiservice_fresh` but was actually hitting LIVE because
`alembic/env.py` had `load_dotenv(override=True)` — explicit env var
overrides on `docker exec` or shell level were silently reset to `.env`
values during alembic startup. Filed as **ASP-DEFECT-021 (RESOLVED)**.
Fix: `load_dotenv(override=False)` — `.env` provides defaults; explicit env
vars win. Standard python-dotenv idiom.

**Atrium-transition note.** `load_dotenv(override=False)` is the required
pattern. `override=True` violates the environment-variable contract and
defeats CI, test isolation, and ad-hoc ops overrides.

**Fresh-DB round-trip result (after fix).** All five mandated steps
produced the expected output:

1. `alembic upgrade head` on empty DB: 23 `"Running upgrade"` lines
   (`-> 0001` through `0022 -> 0023`).
2. `alembic current`: `0023 (head)`.
3. `alembic heads`: `0023 (head)` (single head).
4. `alembic downgrade -1`: `Running downgrade 0023 -> 0022`; `current` → `0022`.
5. `alembic upgrade head`: `Running upgrade 0022 -> 0023`; `current` → `0023 (head)`.

Fresh DB dropped post-test. Live DB unchanged (already at 0023 from earlier apply).

**Live DB state post-migration 023** (verified via `\d tenant_api_keys` and
`\d+ tenants` — recorded in migration phase report):

- `tenant_api_keys`: 11 columns, UNIQUE index on `key_prefix`, composite
  index on `(tenant_id, is_active)`, CHECK `ck_tenant_api_keys_revocation_consistency`
  and `ck_tenant_api_keys_expiry_order`, FK to `tenants(id)` ON DELETE CASCADE.
- Backfill: 1 row — `tenant_id = daa3f639-…`, `key_prefix = 'leg_daa3f639'`,
  `label = 'legacy'`, `is_active = TRUE`, `issued_at = 2026-04-11 03:34:18.557458+00`
  (matches pap_runner's `created_at`).
- `tenants.api_key_hash`: DROPPED.
- `cost_events.caller_feature`: VARCHAR(128) NULL, with index
  `ix_cost_events_caller_feature`.

**Status.** CLOSED — ADR-029 gate satisfied retroactively; migration is
both applied correctly on live and proven reversible in isolation.
Proceeding to I-02 ORM without further ruling per Architect directive.

## 2026-04-18 · Phase 4 — rate limiter + endpoint auth: three engineering decisions

**D-1 — Rate-limit strings as callables, not pre-computed constants.**
`@limiter.limit(INVOKE_RATE)` captures the value at decoration time (app
startup), so mutating `settings.RATE_LIMIT_INVOKE_RPM` at runtime or in
tests had no effect on already-decorated endpoints. Changed `INVOKE_RATE`
and `JOBS_RATE` in `app/gateway/middleware/rate_limiter.py` from module-
level strings to zero-arg functions that read `settings.RATE_LIMIT_*_RPM`
per request. SlowAPI natively accepts callables in `@limiter.limit(...)`.
This preserves AC-S3-05's "activation via env var + restart only; no code
deployment" semantics.

**D-2 — `verify_api_key` is now a side-effecting dependency.**
`@limiter.limit`'s `key_func` is evaluated by SlowAPI's route wrapper
*before* the endpoint body runs. The previous design set
`request.state.tenant_id` inside the endpoint body — by which time the
limiter had already keyed requests by client IP, not tenant_id, causing
tenant B to be throttled because tenant A had saturated the shared IP
bucket (AC-S3-03 FAIL). Fix: `verify_api_key` now accepts `request: Request`
and writes `request.state.tenant_id = str(tenant.id)` on success, before
returning. Tenant_id is therefore on state by end of dependency
resolution — prior to the limiter wrapper — and per-tenant keying works
correctly.

**D-3 — `Header(default=None)` for `X-ASP-API-Key` (spec compliance, not a defect).**
With `Header(...)` (required), FastAPI raised a `RequestValidationError`
for missing headers, handled by the default 422 handler — leaking a
missing auth header as a schema-validation failure. Spec requires 401
RFC 7807 for missing keys. Changed to `Header(default=None, alias=...)`
and added `if x_asp_api_key is None or x_asp_api_key == "": raise
_unauthenticated()` at the top of `verify_api_key`. Missing auth header
now returns 401 RFC 7807 (spec requirement) rather than 422
RequestValidationError (FastAPI default). `Header(default=None)` allows
auth code to run and emit the correct envelope. This is a spec
compliance decision, not a defect.

**Status.** All three decisions shipped in Phase 4 commit. Applied to
`app/gateway/middleware/rate_limiter.py` (D-1), `app/gateway/auth.py`
(D-2, D-3).

