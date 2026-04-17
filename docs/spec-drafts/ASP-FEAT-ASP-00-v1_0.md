# ASP-FEAT-ASP-00 v1.0 — Gateway Service Detailed Spec

**Status:** v1.0-draft COMPLETE — awaiting Product Leadership review
**Spec ID:** ASP-FEAT-ASP-00
**Version:** v1.0
**Template:** ASP-GOV-PLAYBOOK-001 v1.0, Section 5 (14-section template, verbatim)
**Migration head at authoring:** 0022
**Migrations allocated by this spec:** 023 (confirmed with Chief Architect; coverage-aware generation reassigned to 024 when PAP confirms)
**Companion docs:** ADR-001 (service isolation), ADR-006 (cost logging non-fatal), ADR-030 (capability endpoint Zone 2), ADR-032 (multi-key rotation), ADR-034 (OpenAPI export — new, locked by this spec), ASP-GOV-CONSUMPTION-002 (Type C change governance)
**Drafted by:** ASP Development Team (Claude)
**Date:** 2026-04-17
**Reviewer:** Chief Architect & Engineer

---

## §1 Summary

The ASP Gateway (service ID `ASP-00`) is the single external entry point for all AI service invocations across the Atrium platform. It accepts authenticated `POST /api/v1/ai/invoke` requests from consumer modules (PAP, LogiCRM, future internal callers), validates the API key, enforces per-tenant monthly cost quotas and optional per-tenant rate limits, dispatches to the appropriate backend service handler (NLP, Generation, Doc Intelligence, Prediction, Dashboard Intelligence), and emits a cost event on completion. It also exposes `GET /api/v1/ai/jobs/{job_id}` for async job status polling and `GET /api/v1/ai/capabilities` for consumer-side capability discovery per ADR-030. The Gateway owns authentication, quota enforcement, rate limiting, request correlation (`request_id`), cost emission for synchronous services, and uniform RFC 7807 error responses. It does not implement any LLM logic itself — all LLM calls are delegated to service handlers.

## §2 Background and Context

**Why this service exists.** ASP is built as a federation of specialised AI services (ASP-01 through ASP-13). Without a Gateway, every consumer would need to know service-specific endpoints, implement its own auth, discover cost policy, and handle per-service error envelopes — duplicating concerns and leaking the internal service topology into consumer code. The Gateway collapses these cross-cutting concerns into one enforcement point.

**Which phase it belongs to.** ASP-00 is the **foundation-layer** service. Every consumer request hits the Gateway first; every backend service is reached through it. It is the third service to enter formal governance after ASP-01 NLP (GOVERNED 2026-04-10) and ASP-03 Generation (GOVERNED 2026-04-12), which brings the cumulative governance coverage to 3 of 14 services.

**What depends on it.**
- **All consumers:** PAP (`F-03-04`, `F-03-08`, `F-01-10`), LogiCRM (all AI-mediated features), and future callers.
- **All backend services:** routing, cost emission, and quota enforcement are delegated to the Gateway. Services do not authenticate callers themselves.
- **Cost Meter (ASP-08):** every synchronous invocation generates a `cost_event` row via the Gateway's `emit_cost_event_from_gateway` adapter. Async services self-emit on completion.
- **Capabilities discovery (ADR-030):** consumers rely on `GET /api/v1/ai/capabilities` to negotiate supported tasks and schemas before filing consumer-side specs. This response shape is a **Zone 2 contract** (shared with consumers) and is formally governed by this spec.

**Historical drivers.**
- **ASP-NOTE-004/005 (migration drift):** surfaced the need for tighter governance across all services, culminating in the governance onboarding programme of which this spec is the third deliverable.
- **ADR-032 (API key rotation):** locked rotation as a principle in April 2026 but deferred code mechanics to this spec, including multi-key junction table (`tenant_api_keys`) and legacy coexistence during the 90-day Type C window.
- **DEFECT-010 (single-key fragility):** mitigated by the multi-key work in this spec.
- **O(N) auth scan:** current implementation iterates every active tenant's bcrypt hash per call. Measured as ~100 ms × tenant count at each `verify_api_key` invocation. Blocks scale beyond pilot. Solved by the `key_prefix` O(1) lookup approach locked in this spec.
- **Rate-limiting scope ruling (Product Leadership, 2026-04-17):** enables config-driven, per-tenant rate limiting in dormant-by-default posture.
- **F-01-10 unregistered caller_feature (req `d7633490`, 2026-04-16):** PAP sent a `caller_feature` field that ASP's `InvokeRequest` currently drops. Governed in this spec by formal addition of `caller_feature` to the envelope, structlog, and `cost_events` table.

## §3 Scope

### In scope

The scope of v1.0 is the eight items confirmed by the Chief Architect on 2026-04-17:

| # | Scope Item | Deliverable(s) |
|---|---|---|
| S-1 | Auth O(N) fix | New key format `asp_<prefix12>_<secret32>`; `key_prefix` indexed column on `tenant_api_keys`; 1 bcrypt check per request |
| S-2 | Multi-key support (ADR-032 mechanics) | `tenant_api_keys` junction table replacing single `tenants.api_key_hash`; rotation/overlap/revocation semantics |
| S-3 | Rate limiting | SlowAPI + Redis middleware, per-tenant key function, config-driven, disabled by default |
| S-4 | ADR-034 / OpenAPI schema export | `scripts/export_openapi.py`, schema snapshot on every migration, checklist gate |
| S-5 | RFC 7807 error envelope | Uniform `{"type","title","status","detail","instance"}` shape for every Gateway error response |
| S-6 | `caller_feature` field (F-01-10) | Added to `InvokeRequest`; logged in structlog; persisted in `cost_events.caller_feature` |
| S-7 | Capability endpoint governance | Lock `GET /api/v1/ai/capabilities` response shape as Zone 2 contract per ADR-030; define deprecation semantics |
| S-8 | DEFECT-010 resolution | Multi-key overlap window + rotation SOP mechanics (ties into S-2) |

### Out of scope (deferred to v2.0 or later)

- **Dynamic per-tenant rate-limit overrides.** v1.0 ships a single tenant-wide default from config. Per-tenant overrides via `tenants.rate_limit_override_rpm` are deferred.
- **Tenant self-service key management.** v1.0 provides the schema and auth behaviour. An operator-facing `POST /api/v1/admin/tenants/{id}/keys` endpoint is deferred to a future spec.
- **Request hedging / retries at the Gateway.** All retry policy remains per-service (e.g., ASP-03's `llm_call_with_retry`).
- **mTLS or IP-allowlist auth.** Out of scope; API key is the sole auth method in v1.0.
- **OAuth2 client-credentials flow.** Deferred.
- **Request body size limits beyond FastAPI defaults.** Deferred.
- **Gateway-level caching.** Deferred; individual services own their caching (Prompt Registry, Context Store).
- **Capability response localisation.** Response is English-only in v1.0.

### Task list (may expand in TSCDs)

The Gateway exposes no LLM-invoked tasks itself. It routes to tasks owned by backend services:

| Service | Task(s) dispatched |
|---|---|
| `nlp` (ASP-01) | `nl_to_sql`, `intent`, `entity`, `sentiment`, `language`, `classify_probe_result` |
| `generation` (ASP-03) | `draft_email`, `summarise`, `quote`, `suggest`, `whatsapp`, `generate_test_cases`, `generate_test_cases_with_inventory` |
| `doc_intelligence` (ASP-04) | `extract`, `classify` (async) |
| `prediction` (ASP-05) | `churn`, `revenue`, `anomaly`, `lead_scoring` (async) |
| `dashboard_intelligence` (ASP-13) | `interpret`, `narrate`, `anomaly`, `drilldown` |

Consumer requests for `service_type="rag"` are rejected with 422 per ADR-001 (RAG is internal and not gateway-exposed).

## §4 Service Classification

| Attribute | Value |
|---|---|
| **Service ID** | ASP-00 |
| **Service name** | Gateway |
| **Mode** | **Synchronous** for routing, quota enforcement, rate limiting, auth, capability discovery, cost emission. Async handoff delegated to backend services (ASP-04, ASP-05) which self-emit cost events on completion. |
| **LLM calls** | **NONE.** The Gateway performs zero LLM invocations. All model I/O is owned by backend service handlers. |
| **Model tier** | N/A |
| **Internal ASP services called** | Backend handlers in `app.services.*` (`nlp`, `generation`, `doc_intelligence`, `prediction`, `dashboard`); `app.cost.meter` for quota check and cost emission; `app.router_model.model_router` for `quality_tier → model` resolution; `app.infra.db` for session; `app.gateway.auth` for API key verification. |
| **Data stores** | PostgreSQL (`tenants`, `tenant_api_keys`, `cost_events`, `async_jobs`). Redis (rate-limit counters under `slowapi:*` keys; no cache of auth material in v1.0). |
| **Latency budget** | Auth + quota + routing overhead must be ≤ 50 ms p95 (excluding backend service handler time). Measured via `latency_ms` in structlog minus backend handler time. Pre-spec reading: current implementation at pilot scale ≈ 10 ms (dominated by single bcrypt call on cache miss). |
| **Failure domains** | Auth failure (401), unknown service (422), quota exceeded (429), rate-limited (429), handler error (500), upstream timeout (504), upstream overload (502). All rendered in RFC 7807 envelope (§10, §S-5). |
| **Observability** | structlog events: `invoke_start`, `invoke_complete`, `invoke_failed`, `auth_success`, `auth_failed`, `auth_legacy_path_used`, `quota_exceeded`, `rate_limited`, `gateway_cost_emission_failed`. All include `request_id`, `tenant_id`, `caller_module`, `caller_feature`, `service_type`, `task`. |

## §5 Data Model

### Migration required: YES

Migration number: **023** (confirmed with Chief Architect on 2026-04-17; coverage-aware generation reassigned to 024 when PAP confirms).

### Migration 023 — `add_tenant_api_keys_and_key_prefix`

**Effect on schema:**
1. Creates new table `tenant_api_keys` (multi-key junction per ADR-032).
2. Backfills every active `tenants.api_key_hash` into `tenant_api_keys` as a legacy-prefixed row.
3. Drops `tenants.api_key_hash`.
4. Adds `caller_feature VARCHAR(128)` column to `cost_events` (for F-01-10 governance).

### Full Alembic migration source (inline per playbook requirement)

```python
"""Gateway v1.0 — tenant_api_keys junction + caller_feature on cost_events

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-17

Locks ADR-032 code mechanics (multi-key rotation, 90-day Type C window).
Governs F-01-10 caller_feature capture in cost_events.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create tenant_api_keys junction table
    op.create_table(
        "tenant_api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.text("TRUE")),
        sa.Column("label", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tenant_api_keys_prefix", "tenant_api_keys",
                    ["key_prefix"], unique=True)
    op.create_index("ix_tenant_api_keys_tenant", "tenant_api_keys",
                    ["tenant_id", "is_active"], unique=False)

    # Invariant: revocation consistency
    op.create_check_constraint(
        "ck_tenant_api_keys_revocation_consistency",
        "tenant_api_keys",
        "(revoked_at IS NULL AND is_active = TRUE) "
        "OR (revoked_at IS NOT NULL AND is_active = FALSE)",
    )
    # Invariant: expiry order
    op.create_check_constraint(
        "ck_tenant_api_keys_expiry_order",
        "tenant_api_keys",
        "expires_at IS NULL OR expires_at > issued_at",
    )

    # 2. Backfill from tenants.api_key_hash
    # Legacy prefix format: 'legacy' || substr(tenant_id::text, 1, 6)
    # 12 chars total; never matches new-format prefix pattern (lowercase hex after 'legacy')
    op.execute("""
        INSERT INTO tenant_api_keys
            (tenant_id, key_prefix, api_key_hash, label, is_active, issued_at, created_at, updated_at)
        SELECT
            id,
            'legacy' || substr(id::text, 1, 6),
            api_key_hash,
            'legacy',
            is_active,
            created_at,
            created_at,
            now()
        FROM tenants
        WHERE api_key_hash IS NOT NULL;
    """)

    # 3. Drop api_key_hash from tenants (now authoritative in tenant_api_keys)
    op.drop_column("tenants", "api_key_hash")

    # 4. Add caller_feature to cost_events (F-01-10 governance)
    op.add_column(
        "cost_events",
        sa.Column("caller_feature", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_cost_events_caller_feature", "cost_events",
        ["caller_feature"], unique=False,
    )


def downgrade():
    # 4. Remove caller_feature
    op.drop_index("ix_cost_events_caller_feature", table_name="cost_events")
    op.drop_column("cost_events", "caller_feature")

    # 3. Restore api_key_hash on tenants (repopulate from first active key per tenant)
    op.add_column(
        "tenants",
        sa.Column("api_key_hash", sa.String(255), nullable=True),
    )
    op.execute("""
        UPDATE tenants t
        SET api_key_hash = sub.api_key_hash
        FROM (
            SELECT DISTINCT ON (tenant_id) tenant_id, api_key_hash
            FROM tenant_api_keys
            WHERE is_active = TRUE
            ORDER BY tenant_id, issued_at ASC
        ) sub
        WHERE t.id = sub.tenant_id;
    """)
    # Restore NOT NULL only if all rows populated (defensive — downgrade path
    # acceptable even if NOT NULL cannot be re-asserted)
    op.execute("""
        ALTER TABLE tenants
        ALTER COLUMN api_key_hash SET NOT NULL
    """)

    # 2/1. Drop junction table and indexes
    op.drop_index("ix_tenant_api_keys_tenant", table_name="tenant_api_keys")
    op.drop_index("ix_tenant_api_keys_prefix", table_name="tenant_api_keys")
    op.drop_constraint("ck_tenant_api_keys_expiry_order", "tenant_api_keys")
    op.drop_constraint("ck_tenant_api_keys_revocation_consistency", "tenant_api_keys")
    op.drop_table("tenant_api_keys")
```

### Tables added

**`tenant_api_keys`** (new) — multi-key junction per tenant.

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` | Stable row identity |
| `tenant_id` | UUID | FK → `tenants.id` CASCADE, NOT NULL | Multi-key fan-out (ADR-032) |
| `key_prefix` | VARCHAR(12) | NOT NULL, UNIQUE INDEX | O(1) lookup replacing O(N) scan |
| `api_key_hash` | VARCHAR(255) | NOT NULL | bcrypt hash of full key (including prefix) |
| `issued_at` | TIMESTAMPTZ | NOT NULL, default `now()` | Audit / rotation-age metrics |
| `expires_at` | TIMESTAMPTZ | Nullable | Optional hard expiry; NULL = no expiry |
| `revoked_at` | TIMESTAMPTZ | Nullable | Hard revoke timestamp for forensics |
| `is_active` | BOOLEAN | NOT NULL, default TRUE | Fast-path filter |
| `label` | VARCHAR(64) | Nullable | Operator-facing name (e.g. `pap_runner`, `ci-2026Q2`) |
| `created_at`, `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` | Standard audit columns |

Invariants (CHECK constraints):
- `ck_tenant_api_keys_revocation_consistency` — `is_active=FALSE` ⇔ `revoked_at IS NOT NULL`
- `ck_tenant_api_keys_expiry_order` — `expires_at > issued_at` when set

Indexes:
- `ix_tenant_api_keys_prefix` — UNIQUE on `key_prefix` (hot path)
- `ix_tenant_api_keys_tenant` — composite on `(tenant_id, is_active)` (rotation queries, revocation queries)

### Tables amended

**`tenants`**
- Drops `api_key_hash` (authoritative source moves to `tenant_api_keys`).
- All other columns unchanged (`id`, `tenant_code`, `name`, `monthly_quota_usd`, `is_active`, `created_at`, `updated_at`).

**`cost_events`**
- Adds `caller_feature VARCHAR(128)` NULL (F-01-10 governance; per §S-6 and §7).
- Index `ix_cost_events_caller_feature` for future cost-by-feature analytics.
- **Governed semantics of NULL:** `caller_feature IS NULL` means (a) the row was inserted before this migration applied, or (b) the caller did not send a `caller_feature` field (e.g. LogiCRM callers not yet adopting the field, or internal ASP callers). NULL is **NOT** a data quality issue and MUST NOT be reported as such by observability dashboards. Analytics queries SHOULD use `COALESCE(caller_feature, '<unknown>')` when grouping. This semantic is locked by ADR-032 amendment and forms AC-S6-04.

### Tables unchanged

`prompt_templates`, `async_jobs`, `webhook_registrations`, `cost_monthly_reports`, `conversation_contexts` (Redis), all other existing tables.

### ORM changes (for `app/models/db_models.py`)

```python
class TenantApiKey(Base):
    __tablename__ = "tenant_api_keys"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id    = Column(UUID(as_uuid=True),
                          ForeignKey("tenants.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    key_prefix   = Column(String(12),  nullable=False, unique=True, index=True)
    api_key_hash = Column(String(255), nullable=False)
    issued_at    = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at   = Column(DateTime(timezone=True), nullable=True)
    revoked_at   = Column(DateTime(timezone=True), nullable=True)
    is_active    = Column(Boolean, nullable=False, default=True)
    label        = Column(String(64), nullable=True)
    created_at   = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at   = Column(DateTime(timezone=True), nullable=False, default=utcnow,
                          onupdate=utcnow)
    tenant = relationship("Tenant", back_populates="api_keys")


# On Tenant:
    api_keys = relationship("TenantApiKey", back_populates="tenant",
                            cascade="all, delete-orphan")
# Remove: api_key_hash = Column(String(255), nullable=False)


# On CostEvent:
    caller_feature = Column(String(128), nullable=True, index=True)
```

### Post-sunset migration (planned; not written in v1.0)

At T+90 days from spec acceptance (ADR-032 Type C window close), a separate migration removes legacy rows:

```sql
DELETE FROM tenant_api_keys WHERE key_prefix LIKE 'legacy%';
```

This migration is tracked as Closure AC-Close-03 (§12) and is a binding post-acceptance action. It does NOT consume a v1.0 migration number — it will be allocated at T+90 based on the migration head at that point.

### Pre-write gate confirmation

| Gate | Status | Evidence |
|---|---|---|
| G-1 Schema | Verified — mapped all 11 new columns to their backing PG types | §5 table |
| G-2 Types | `VARCHAR(12)`, `VARCHAR(255)`, `TIMESTAMPTZ`, `BOOLEAN`, `UUID` — all standard, no mismatch risk | migration source |
| G-3 Contract | Response shape impact: none on `/ai/invoke` (auth is upstream). Internal ORM change only | §6, §7 |
| G-4 Audit | CHECK constraints declared before any INSERT path uses the table | migration source |
| G-5 Migration | Confirmed `down_revision = "0022"`; single head after apply | migration source |
| G-6 Frontend | N/A (Gateway has no UI) | — |
| G-7 Dependency | ORM imports `TenantApiKey`; auth.py imports it; `Tenant.api_keys` relationship added | §6, §10 |

---

## §6 API Contract

The Gateway exposes **four external endpoints**. All are served under prefix `/api/v1/ai`. All share the same auth dependency (`verify_api_key`, dual-path per §10). Rate-limit behaviour and error matrix differ per endpoint.

### Endpoint inventory

| # | Method & Path | Purpose | Auth | Rate limit (config) | Async? | Owner |
|---|---|---|---|---|---|---|
| E-1 | `POST /api/v1/ai/invoke` | Invoke an AI task on a backend service | `X-ASP-API-Key` required | `RATE_LIMIT_INVOKE_RPM` (default 60/min per tenant) | Sync for `{nlp, generation, dashboard_intelligence}`; returns 202 + `job_id` for `{doc_intelligence, prediction}` | Gateway |
| E-2 | `GET /api/v1/ai/jobs/{job_id}` | Poll async job status | `X-ASP-API-Key` required | `RATE_LIMIT_JOBS_RPM` (default 120/min per tenant) | Always sync | Gateway |
| E-3 | `GET /api/v1/ai/capabilities` | Discover supported tasks, models, schemas (ADR-030 Zone 2) | `X-ASP-API-Key` required | **No limit** (read-only, low cost, used during caller bootstrap) | Sync | Gateway |
| E-4 | `GET /api/v1/ai/schemas/{service_type}/{task}` | Retrieve the payload + result JSON Schema for a specific task | `X-ASP-API-Key` required | **No limit** (read-only, low cost, consumed by caller specs and SDK generators) | Sync | Gateway |

Internal service-to-service calls (Gateway → handler) are Python function calls, not HTTP. Those are documented in §7 and governed via the in-process `SERVICE_MAP` dispatch.

### E-1 — `POST /api/v1/ai/invoke`

**Request envelope:** `InvokeRequest` (see §7 for full schema delta governing `caller_feature`).
**Success response (sync services):** `InvokeResponse` (200 OK).
**Success response (async services):** `JobAcceptedResponse` (202 Accepted with `job_id` + `request_id`).
**Headers in:** `X-ASP-API-Key` (required), `Content-Type: application/json` (required).
**Headers out:** `X-Request-Id` (echoes `request_id` from response body).

**Error matrix (RFC 7807 envelope per §10, §S-5):**

| HTTP | `type` | `title` | Cause | Retryable by caller? |
|---|---|---|---|---|
| 400 | `/errors/invalid-request` | Invalid request | JSON parse error, required fields missing | No |
| 401 | `/errors/unauthenticated` | Invalid or missing API key | Auth failure (both paths exhausted) | No |
| 422 | `/errors/unsupported-service` | Unsupported service_type | `service_type` not in `SERVICE_MAP` (includes RAG per ADR-001) | No |
| 422 | `/errors/validation-failed` | Request validation failed | Pydantic validation failure on payload | No |
| 429 | `/errors/quota-exceeded` | Monthly quota exceeded | `check_quota` returned False | No (wait for cycle) |
| 429 | `/errors/rate-limited` | Rate limit exceeded | SlowAPI decision (when `RATE_LIMIT_ENABLED=True`) | Yes (respect `Retry-After`) |
| 500 | `/errors/internal` | Internal error | Unhandled exception in handler | Idempotent retry allowed |
| 502 | `/errors/upstream-bad-gateway` | Upstream model error | Anthropic 5xx after exhausted retries | Retry after backoff |
| 504 | `/errors/upstream-timeout` | Upstream model timeout | Anthropic timeout / connection error | Retry after backoff |

### E-2 — `GET /api/v1/ai/jobs/{job_id}`

**Path parameter:** `job_id` (string; UUID v4 format expected but not enforced at route level).
**Success response:** `JobStatusResponse` (200 OK).
**Tenant scoping:** query filters by both `job_id` AND `tenant_id = <authenticated tenant>`. Cross-tenant job_id returns 404, never 403 — see §10 (ADR-012).

**Error matrix:**

| HTTP | `type` | `title` | Cause |
|---|---|---|---|
| 401 | `/errors/unauthenticated` | Invalid or missing API key | Auth failure |
| 404 | `/errors/job-not-found` | Job not found | `job_id` does not exist OR belongs to a different tenant |
| 429 | `/errors/rate-limited` | Rate limit exceeded | SlowAPI decision |
| 500 | `/errors/internal` | Internal error | DB connection failure, ORM exception |

### E-3 — `GET /api/v1/ai/capabilities` (ADR-030, Zone 2)

**Query parameters:** none in v1.0.
**Success response (200 OK):**

```json
{
  "asp_version": "1.0.0",
  "capabilities_schema_version": "1",
  "services": [
    {
      "service_type": "nlp",
      "sync": true,
      "tasks": ["nl_to_sql", "intent", "entity", "sentiment", "language", "classify_probe_result"],
      "status": "GOVERNED",
      "governance_spec": "ASP-FEAT-ASP-01 v1.2"
    },
    {
      "service_type": "generation",
      "sync": true,
      "tasks": ["draft_email", "summarise", "quote", "suggest", "whatsapp",
                "generate_test_cases", "generate_test_cases_with_inventory"],
      "status": "GOVERNED",
      "governance_spec": "ASP-FEAT-ASP-03 v1.1"
    },
    { "service_type": "doc_intelligence", "sync": false,
      "tasks": ["extract", "classify"], "status": "COMPLETE" },
    { "service_type": "prediction", "sync": false,
      "tasks": ["churn", "revenue", "anomaly", "lead_scoring"], "status": "COMPLETE" },
    { "service_type": "dashboard_intelligence", "sync": true,
      "tasks": ["interpret", "narrate", "anomaly", "drilldown"], "status": "COMPLETE" }
  ],
  "deprecated_tasks": []
}
```

**Governance of this response shape (ADR-030):**

- **Zone 2 contract** — shared between ASP and all consumers. Every field is a Zone 2 surface.
- **Additive changes (new services, new tasks, new top-level keys):** Type B. Consumers MUST ignore unknown fields per forward-compat discipline.
- **Removals (tasks, services, top-level keys):** Type C. Require 90-day deprecation window; the removed task/service MUST appear in `deprecated_tasks[]` for the full window with `sunset_date`.
- **Field-name or field-type changes:** Type C. Same window rules.
- **`capabilities_schema_version`:** bumped on any Type B or Type C change. Consumers SHOULD pin against this version.

### E-4 — `GET /api/v1/ai/schemas/{service_type}/{task}`

**Path parameters:**
- `service_type` — one of the five governed values (same Literal as `InvokeRequest.service_type`); `rag` returns 422.
- `task` — any task owned by that service (see E-3 capability response).

**Success response (200 OK):**

```json
{
  "service_type": "generation",
  "task": "generate_test_cases_with_inventory",
  "payload_schema": { /* JSON Schema draft-07 */ },
  "result_schema":  { /* JSON Schema draft-07 */ },
  "prompt_contract_version": "v3",
  "governance_spec": "ASP-FEAT-ASP-03 v1.1"
}
```

**Error matrix:**

| HTTP | `type` | `title` | Cause |
|---|---|---|---|
| 401 | `/errors/unauthenticated` | Invalid or missing API key | Auth failure |
| 422 | `/errors/unsupported-service` | Unsupported service_type | Not in `SERVICE_MAP` (includes `rag`) |
| 404 | `/errors/task-not-found` | Task not found | `task` not registered for this `service_type` |
| 500 | `/errors/internal` | Internal error | Schema generation failure |

**Schema source:** generated from Pydantic models at request time (not cached in v1.0 — volume is low). ADR-034 (OpenAPI export) produces the full set at migration time for external distribution.

### RFC 7807 error envelope — Zone 2 shared contract (Type B additive)

**Classification:** Type B (additive) per ASP-GOV-CONSUMPTION-002.

**Why Type B and not Type C:** existing consumers (notably PAP) already parse `detail` and `request_id` from error responses. The new envelope adds `type`, `title`, `status`, `instance` and keeps `detail` and `request_id` intact with the same semantics. No existing field is renamed, removed, or retyped. Therefore no deprecation window is required; the change is deployed atomically with spec acceptance and PAP's existing error handling continues to work unchanged.

**Envelope shape (uniform across all endpoints, all error HTTP codes):**

```json
{
  "type":     "/errors/unauthenticated",
  "title":    "Invalid or missing API key",
  "status":   401,
  "detail":   "Provided API key did not match any active credential",
  "instance": "/api/v1/ai/invoke",
  "request_id": "f6a1e0c8-2d90-4a3f-9b8e-4c9d7f2a6111"
}
```

Field semantics:

| Field | Source | Stability |
|---|---|---|
| `type` | From error matrix above. Stable URI-style identifier. | Part of Zone 2 contract; changes are Type C. |
| `title` | Short human-readable summary. | Part of Zone 2 contract (stable text). |
| `status` | Matches HTTP status. | Hard-linked to HTTP code. |
| `detail` | Dynamic, per-request. May reference IDs, counts, etc. | Informational; consumers MUST NOT parse. |
| `instance` | The request path (not including query). | Deterministic. |
| `request_id` | Correlation ID; present on error paths where a request was accepted. Absent on pre-auth errors where no request_id was allocated. | Matches `X-Request-Id` response header when present. |

**PAP impact statement:** PAP's current error handler reads `detail` for display text and `request_id` for support correlation. Both fields retain their exact existing semantics. No PAP code change is required for error parsing. PAP SHOULD adopt `type` for structured error classification at its convenience (no deadline).

## §7 Request / Response Detail

### `InvokeRequest` schema delta (governs `caller_feature`)

**Governance note (first-time field):** this spec introduces `caller_feature` to governed state. It is added to `InvokeRequest` as an **optional string field**, Type B additive per ASP-GOV-CONSUMPTION-002. Existing callers continue to work unchanged; callers MAY begin sending it immediately upon deployment; ASP-side capture is mandatory.

**Full field spec for `caller_feature`:**

| Attribute | Value |
|---|---|
| **Name** | `caller_feature` |
| **Type (Python)** | `Optional[str] = None` |
| **Type (JSON Schema)** | `{"type": ["string", "null"], "maxLength": 128}` |
| **Location** | Top-level field on `InvokeRequest` (not inside `payload`, not inside `user_context`) |
| **Max length** | 128 chars (matches `cost_events.caller_feature` column width) |
| **Required** | No |
| **Default** | `None` |
| **Validated against a known list?** | **No.** ASP does not maintain a registry of valid caller_feature values. The field is opaque to ASP routing and validation. |
| **Used for routing?** | **No.** Routing is by `service_type` + `task` only. |
| **Used for prompt selection?** | **No.** Prompt Registry keys on `(service_type, task, caller_module, maturity_level)` per ADR-007. |
| **Used for cost tracking?** | **Yes.** Persisted to `cost_events.caller_feature` verbatim (or NULL if not provided). |
| **Used for observability?** | **Yes.** Logged in structlog on `invoke_start`, `invoke_complete`, `invoke_failed`. |
| **Type C change implication** | None in v1.0. Future introduction of required enum would be Type C. |

**What ASP does with it (normative):**

1. Accept the field on `InvokeRequest` (Pydantic validates type and max length).
2. Bind it to the structlog logger context alongside `caller_module` for every Gateway log event in the request lifecycle.
3. Pass it through to `emit_cost_event_from_gateway`, which writes it to `cost_events.caller_feature`.
4. **Do nothing else.** No routing, no prompt selection, no validation against any list, no authorisation decision.

**What ASP does NOT do with it (normative):**

1. Does not reject requests with unknown `caller_feature` values.
2. Does not require it even when `caller_module` is known to populate it (PAP).
3. Does not surface it back to the caller in `InvokeResponse`.
4. Does not persist it anywhere other than `cost_events`.
5. Does not include it in prompt templates or backend service handlers unless a future spec explicitly requires it.

### Updated `InvokeRequest` (full model with delta highlighted)

```python
class InvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_type: Literal[
        "nlp", "generation", "doc_intelligence", "prediction", "dashboard_intelligence"
    ]
    task: str
    caller_module: str
    caller_feature: Optional[str] = Field(default=None, max_length=128)   # NEW — S-6 / F-01-10
    tenant_id: str
    quality_tier: Literal["standard", "enhanced", "premium"] = "standard"
    session_id: Optional[str] = None
    user_context: Optional[UserContext] = None
    ui_context: Optional[UIContext] = None
    conversation_history: list[ConversationTurn] = []
    schema_hints: Optional[SchemaHints] = None
    payload: dict[str, Any]
```

### `InvokeResponse` — no change

`InvokeResponse` is unchanged by this spec. `caller_feature` is a request-only field.

### `JobStatusResponse` — no change

`JobStatusResponse` is unchanged by this spec.

### `CapabilitiesResponse` — new, governed

First appearance in governed state. Pydantic model:

```python
class ServiceCapability(BaseModel):
    service_type: str
    sync: bool
    tasks: list[str]
    status: Literal["COMPLETE", "GOVERNED"]
    governance_spec: Optional[str] = None

class DeprecatedTask(BaseModel):
    service_type: str
    task: str
    sunset_date: str    # ISO-8601 date

class CapabilitiesResponse(BaseModel):
    asp_version: str
    capabilities_schema_version: str
    services: list[ServiceCapability]
    deprecated_tasks: list[DeprecatedTask] = []
    # Note: migration_head is operational-internal (Zone 1) and intentionally
    # NOT exposed here. Consumers requiring it use GET /health (operator-facing).
```

### `TaskSchemaResponse` — new, governed

```python
class TaskSchemaResponse(BaseModel):
    service_type: str
    task: str
    payload_schema: dict[str, Any]   # JSON Schema draft-07
    result_schema: dict[str, Any]    # JSON Schema draft-07
    prompt_contract_version: Optional[str] = None
    governance_spec: Optional[str] = None
```

### `result{}` structure per task

The Gateway does not own task-specific `result{}` shapes. These are owned by the governing spec for each backend service (ASP-FEAT-ASP-01 v1.2, ASP-FEAT-ASP-03 v1.1, etc.). The Gateway's contribution is the `InvokeResponse` envelope around `result`.

### structlog event schema — delta for `caller_feature`

All Gateway log events in the request lifecycle bind `caller_feature` when present:

```
invoke_start      request_id tenant_id caller_module caller_feature service_type task model
invoke_complete   request_id tenant_id latency_ms
invoke_failed     request_id tenant_id caller_module caller_feature error [exc_info]
auth_success      path tenant_id
auth_failed       path [prefix]
auth_legacy_path_used  key_shape sunset
quota_exceeded    request_id tenant_id quota_usd
rate_limited      request_id tenant_id endpoint retry_after_s
gateway_cost_emission_failed  request_id tenant_id caller_module caller_feature error
```

## §8 Caller Integration Guide

### Request envelope construction (authoritative)

Callers (PAP, LogiCRM, future consumers) construct `InvokeRequest` as follows:

| Field | Who sets it | Required | Notes |
|---|---|---|---|
| `service_type` | Caller | Yes | One of the five governed values. `rag` is rejected with 422. |
| `task` | Caller | Yes | Must be a task registered for the chosen `service_type` (see E-3 capabilities). |
| `caller_module` | Caller | Yes | Module ID: `PAP`, `LogiCRM`, `internal`, etc. Governed by ADR-007. |
| `caller_feature` | Caller | **No** | Optional string, ≤ 128 chars. When populated, identifies a specific feature within the calling module (e.g. PAP's `F-03-04`, `F-03-08`, `F-01-10`). See §7 for full semantics. |
| `tenant_id` | Caller | Yes | Must match the authenticated tenant (enforced at Gateway). Cross-tenant values rejected. |
| `quality_tier` | Caller | No | Defaults to `"standard"`. |
| `session_id` | Caller | No | For conversation continuity (ASP-07 Context Store). |
| `user_context` | Caller | Conditional | Required for RBAC-sensitive tasks (NLP `nl_to_sql`, etc. — per service spec). |
| `ui_context` | Caller | Conditional | Required when schema_hints rely on active screen. |
| `conversation_history` | Caller | No | Multi-turn support. |
| `schema_hints` | Caller | Conditional | Required for `service_type=nlp` / `task=nl_to_sql`. |
| `payload` | Caller | Yes | Service-specific; validated by backend handler. |

### Required context fields — reiterated from per-service governed specs

- **For `service_type="nlp"`:** see ASP-FEAT-ASP-01 v1.2 §8 (RBAC + schema_hints mandatory on `nl_to_sql`).
- **For `service_type="generation"`:** see ASP-FEAT-ASP-03 v1.1 §8 (caller_module and payload-specific schemas per task).
- **For other services:** see their respective governed specs (or the service classification in §4 of their detailed spec).

### Consumer-side bootstrap sequence (recommended)

1. Consumer calls `GET /api/v1/ai/capabilities` at startup and at config-reload.
2. Consumer pins against `capabilities_schema_version`; logs a warning if remote version differs.
3. For each `(service_type, task)` the consumer will call, consumer calls `GET /api/v1/ai/schemas/{service_type}/{task}` and caches the payload/result schemas locally.
4. Consumer constructs `InvokeRequest` against the cached schema; sends `POST /api/v1/ai/invoke`.
5. On 422 with `type=/errors/validation-failed`, consumer re-fetches the schema (in case of stale cache across a Type B additive change).
6. On 422 with `type=/errors/unsupported-service` or `/errors/task-not-found`, consumer surfaces this as a capability-mismatch and does NOT retry.
7. On async services (`doc_intelligence`, `prediction`), consumer receives 202 with `job_id`, then polls E-2 with configurable backoff until `status ∈ {completed, failed}`.

### API key handling

- **New-format keys:** `asp_<prefix12>_<secret32>`. Consumers MUST transmit the full key in `X-ASP-API-Key` header; MUST NOT log or persist the full key in plaintext; MAY safely log the prefix (first 16 chars: `asp_<prefix12>`) for correlation.
- **Legacy-format keys:** any key not matching `^asp_[a-z0-9]{12}_[A-Za-z0-9]{32}$`. These continue to authenticate during the 90-day Type C window following spec acceptance. Consumers SHOULD treat legacy keys as deprecated and request re-issuance within the window.
- **Rotation:** when a new key is issued to overlap an old one, both authenticate concurrently until the operator revokes the old one. Consumers SHOULD deploy the new key, verify success, then coordinate revocation of the old key with the ASP operator.

### Rate limiting (when `RATE_LIMIT_ENABLED=True`)

- Limits are enforced per tenant (not per IP).
- 429 responses include a `Retry-After` header in seconds.
- Consumers MUST respect `Retry-After`; retrying faster may result in temporary suspension at the tenant-quota layer.
- The `GET /ai/capabilities` and `GET /ai/schemas` endpoints are **not rate-limited** and MAY be called freely during bootstrap.

## §9 LLM and Prompt Design

**N/A — the Gateway makes no LLM calls.** All LLM invocations are owned by backend service handlers (ASP-01 NLP, ASP-03 Generation, etc.) and governed by their respective detailed specs; the Gateway is a routing, enforcement, and observability layer with zero model I/O.

## §10 Security Requirements

### Timestamp convention (universal)

All datetime values in this spec and the governed implementation are timezone-aware UTC per ADR-009. Generation uses `datetime.now(timezone.utc)`; DB columns are `TIMESTAMPTZ`. This is stated once here and applies to every method, migration, and handler in the Gateway — it is not repeated per call site.

### Auth requirement on capabilities and schemas endpoints (E-3, E-4) — security rationale

`GET /api/v1/ai/capabilities` and `GET /api/v1/ai/schemas/{service_type}/{task}` are **not public**. They require a valid `X-ASP-API-Key` for the following reason:

- **They reveal the full service and task inventory** (E-3) and the **Pydantic payload/result schemas** (E-4). In combination this is sufficient to craft targeted malformed payloads, probe for validation regressions, and enumerate the attack surface without generating any cost or rate-limit signal.
- **Making them public would shift Gateway surface area from "authenticated reconnaissance" to "unauthenticated reconnaissance"** — a strictly worse security posture with no operational benefit (consumers already hold an API key by the time they bootstrap).
- **Consumer rate-limit exemption remains intact** (E-3/E-4 are not rate-limited) — auth does not impose a throttling burden on bootstrap.

This rationale is recorded here so that future TSCDs do not quietly remove the auth requirement without a documented reason. Any proposal to make E-3 or E-4 public MUST cite this paragraph and produce a compensating control.

### Tenant isolation (ADR-012, ADR-013)

- **Every** request path through the Gateway resolves a `tenant` object via `verify_api_key` and binds `tenant_id` to the request context.
- `POST /api/v1/ai/invoke` passes `tenant` into the backend handler; handlers query all data scoped by `tenant_id`.
- `GET /api/v1/ai/jobs/{job_id}` filters `AsyncJob.tenant_id == tenant.id`; cross-tenant `job_id` returns 404 (not 403) per ADR-012 — do not leak job existence across tenants.
- `GET /api/v1/ai/capabilities` and `GET /api/v1/ai/schemas/{service_type}/{task}` return identical data for every authenticated tenant in v1.0 (capabilities are platform-wide, not tenant-scoped).

### Authentication (ADR-014, ADR-032)

**Dual-path `verify_api_key`** during the 90-day Type C window:

```python
async def verify_api_key(
    x_asp_api_key: str = Header(..., alias="X-ASP-API-Key"),
) -> Tenant:
    """
    Dual-path auth during ADR-032 Type C window (sunset: <acceptance_date + 90d>).
      - New format   asp_<prefix12>_<secret32>  → O(1) prefix lookup + 1 bcrypt check
      - Legacy       anything else              → O(N) scan across legacy-prefixed rows
    Always returns the Tenant or raises 401. Never 403 on auth failure.
    """
    key = x_asp_api_key

    # --- Fast path: new format ------------------------------------------
    if _is_new_format(key):   # regex: r"^asp_[a-z0-9]{12}_[A-Za-z0-9]{32}$"
        prefix = key[4:16]
        async with get_session() as session:
            row = (await session.execute(
                select(TenantApiKey).where(
                    TenantApiKey.key_prefix == prefix,
                    TenantApiKey.is_active == True,
                )
            )).scalar_one_or_none()
            if (row
                and _not_expired(row)
                and bcrypt.checkpw(key.encode(), row.api_key_hash.encode())):
                tenant = await session.get(Tenant, row.tenant_id)
                if tenant and tenant.is_active:
                    log.info("auth_success", path="new_format",
                             tenant_id=str(tenant.id))
                    return tenant
        log.warning("auth_failed", path="new_format", prefix=prefix)
        # HTTPException.detail is a simple string; the global exception
        # handler (I-RFC7807) renders the RFC 7807 envelope at the top level.
        raise HTTPException(401, detail="Invalid or missing API key")

    # --- Slow path: legacy (sunset <date>) ------------------------------
    log.warning("auth_legacy_path_used", key_shape="legacy",
                sunset="<ACCEPT+90d>")
    async with get_session() as session:
        legacy_rows = (await session.execute(
            select(TenantApiKey).where(
                TenantApiKey.key_prefix.like("legacy%"),
                TenantApiKey.is_active == True,
            )
        )).scalars().all()
        for row in legacy_rows:
            if bcrypt.checkpw(key.encode(), row.api_key_hash.encode()):
                tenant = await session.get(Tenant, row.tenant_id)
                if tenant and tenant.is_active:
                    log.info("auth_success", path="legacy",
                             tenant_id=str(tenant.id))
                    return tenant

    raise HTTPException(401, detail="Invalid or missing API key")
```

Key-format parser:

```python
import re
_NEW_FORMAT_RE = re.compile(r"^asp_[a-z0-9]{12}_[A-Za-z0-9]{32}$")
def _is_new_format(key: str) -> bool:
    return bool(_NEW_FORMAT_RE.match(key))

def _not_expired(row: "TenantApiKey") -> bool:
    if row.expires_at is None:
        return True
    return row.expires_at > datetime.now(timezone.utc)
```

### Key format and generation (S-1)

- **Format:** `asp_<prefix12>_<secret32>` — 50 chars total.
- **Prefix:** 12 chars, charset `[a-z0-9]` (base36), ~62 bits, UNIQUE enforced at DB.
- **Secret:** 32 chars, charset `[A-Za-z0-9]` (base62), ~190 bits.
- **Generation (operator-side, not exposed in v1.0):**

```python
import secrets, string
def issue_new_key() -> tuple[str, str]:
    """Returns (full_key_plaintext, prefix). Prefix stored in DB; full key bcrypted."""
    alphabet36 = string.digits + "abcdefghijklmnopqrstuvwxyz"
    alphabet62 = alphabet36 + string.ascii_uppercase
    prefix = "".join(secrets.choice(alphabet36) for _ in range(12))
    secret = "".join(secrets.choice(alphabet62) for _ in range(32))
    return f"asp_{prefix}_{secret}", prefix
```

- Collision probability at pilot scale (≤100 tenants × ≤10 keys/tenant = 1000 keys): negligible (36¹² ≈ 4.7×10¹⁸). Issuance code MAY retry on UNIQUE violation; simpler alternative is single-shot issuance with the DB constraint as the canonical guard.

### Rotation and revocation (ADR-032 mechanics, DEFECT-010 resolution)

1. **Issue new key for tenant T:** operator creates `tenant_api_keys` row with fresh prefix/hash; `is_active=TRUE`, `revoked_at=NULL`. Old row remains active.
2. **Overlap window:** both keys authenticate.
3. **Consumer acknowledgement:** consumer deploys new key, verifies at least one successful authenticated request (observed via structlog `auth_success` on the new prefix). Consumer signals acknowledgement to operator out-of-band (ticket / email).
4. **Revoke old key:** operator sets `is_active=FALSE`, `revoked_at=now()`. CHECK constraint enforces consistency. Auth now fails for the old key.
5. **Audit trail:** the row remains in place for audit (soft delete). Hard delete never executed in v1.0 except by the post-sunset legacy-cleanup migration.

### Data handling (ADR-015, ADR-016)

- Gateway does not persist request or response bodies beyond the cost_event row (tokens, cost, latency, request_id, tenant_id, caller_module, caller_feature, service_type, task — no raw payload).
- `X-ASP-API-Key` is never logged. Structlog binds only the prefix (first 16 chars of the new format) or a `key_shape="legacy"` marker.
- Rate-limiter state in Redis uses keys of the form `slowapi:invoke:<tenant_id>` and `slowapi:jobs:<tenant_id>` — no auth material.

### Error-path information leakage

- 401 body contains only the generic envelope; it MUST NOT reveal whether the prefix was found, whether `is_active` was false, whether expiry fired, or which tenant was targeted.
- 404 for cross-tenant `job_id` MUST be indistinguishable from 404 for non-existent `job_id`.
- 422 MAY enumerate supported values (e.g. `service_type` list) — these are already public via capabilities.

### Rate limiter security properties

- Keyed by `tenant_id` (not by IP). An attacker controlling multiple IPs under the same tenant cannot exceed tenant-wide RPM.
- Rate limiter runs **after** auth. Unauthenticated callers contribute to the shared `get_remote_address` bucket as a courtesy degradation; they never exhaust tenant-specific quota.
- When `RATE_LIMIT_ENABLED=False`, the limiter is fully dormant (no Redis writes, no decisions) — validated by AC-S3-04.

### Universal ADR references

Per playbook §7, ADRs 012–016 are universal to all ASP services and apply here by reference:

- ADR-012 — Cross-tenant returns 404, never 403.
- ADR-013 — Tenant-scoping on every DB query.
- ADR-014 — API key in header, bcrypted at rest.
- ADR-015 — No raw payload persistence beyond cost events.
- ADR-016 — Structlog never binds secrets.

ADRs introduced or extended by this spec: ADR-030 (Zone 2 capabilities, formally governed), ADR-032 (multi-key mechanics, locked), ADR-034 (OpenAPI export on migration, new — registered in §11).

---

**End of Batch 2 (§6–§10). Batch 3 follows.**

---

## §11 Implementation Checklist

All tasks are owned by the ASP Development Team unless noted. Order below is the recommended execution order; numbered labels are stable identifiers referenced in §12 ACs.

### I-RFC7807 — RFC 7807 global exception handler (implement FIRST)

**Why first:** the handler must exist before any endpoint raises `HTTPException`, because every error path in this spec relies on it to render the top-level `application/problem+json` envelope. Without it, errors are emitted as FastAPI's default `{"detail": ...}` shape — a Zone 2 contract violation on day one.

**New file: `app/gateway/exception_handlers.py`**

```python
"""RFC 7807 global exception handler — renders top-level problem+json envelope
for every HTTPException raised within the Gateway.

Per ASP-FEAT-ASP-00 v1.0 §6 and §10, the envelope shape is:
    {type, title, status, detail, instance, request_id}
with Content-Type: application/problem+json.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

_STATUS_TITLES = {
    400: "Bad Request",
    401: "Unauthorised",
    404: "Not Found",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    504: "Gateway Timeout",
}


async def http_exception_handler(request: Request, exc: HTTPException):
    detail_text: str
    if isinstance(exc.detail, str):
        detail_text = exc.detail
    elif isinstance(exc.detail, dict):
        detail_text = exc.detail.get("detail", "An error occurred")
    else:
        detail_text = "An error occurred"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type":       f"https://asp.internal/errors/{exc.status_code}",
            "title":      _STATUS_TITLES.get(exc.status_code, "Error"),
            "status":     exc.status_code,
            "detail":     detail_text,
            "instance":   str(request.url.path),
            "request_id": getattr(request.state, "request_id", None),
        },
        media_type="application/problem+json",
    )
```

**Wire-up in `app/main.py`:**

```python
from fastapi.exceptions import HTTPException
from app.gateway.exception_handlers import http_exception_handler

app.add_exception_handler(HTTPException, http_exception_handler)
```

Validation AC: AC-S5-01 through AC-S5-06 (§12).

### I-01 — Migration 023 (`add_tenant_api_keys_and_key_prefix`)

- Write migration file at `alembic/versions/0023_add_tenant_api_keys_and_key_prefix.py` using the full source in §5.
- Apply locally, verify single head, run `alembic current`.
- Verify `tenant_api_keys` exists with 11 columns, both indexes, both CHECK constraints.
- Verify `tenants.api_key_hash` dropped.
- Verify `cost_events.caller_feature` added with `ix_cost_events_caller_feature`.
- Verify backfill: every previously active tenant has exactly one row in `tenant_api_keys` with `key_prefix LIKE 'legacy%'`.
- Update `CLAUDE.md` applied chain; update `ASP-SCHEMA-CURRENT.md`; update `ASP-INDEX.md` migration head.

### I-02 — ORM changes (`app/models/db_models.py`)

- Remove `api_key_hash` column from `Tenant`.
- Add `api_keys` relationship on `Tenant` with `cascade="all, delete-orphan"`.
- Add new `TenantApiKey` class per §5.
- Add `caller_feature: Optional[str]` column to `CostEvent` with index.
- Gate 7 check: `python -c 'from app.models.db_models import TenantApiKey, Tenant, CostEvent'` imports clean.

### I-03 — New key format + key generation utility (`app/gateway/keys.py`)

- New file `app/gateway/keys.py` containing:
  - `_NEW_FORMAT_RE` compiled regex `r"^asp_[a-z0-9]{12}_[A-Za-z0-9]{32}$"`.
  - `def is_new_format(key: str) -> bool`.
  - `def issue_new_key() -> tuple[str, str]` using `secrets.choice` over base36 (prefix) and base62 (secret). Returns `(full_key_plaintext, prefix)`.
- Unit tests in `tests/gateway/test_keys.py` covering:
  - Format regex accepts well-formed keys and rejects malformed variants.
  - `issue_new_key()` always returns a 50-char key with the expected structure.
  - Prefix-only logging never contains the secret portion.

### I-04 — Dual-path `verify_api_key` (`app/gateway/auth.py`)

- Rewrite `verify_api_key` per §10. Both paths share the FastAPI `Header(..., alias="X-ASP-API-Key")` dependency.
- New-format path: O(1) `WHERE key_prefix = ?` + single `bcrypt.checkpw`.
- Legacy path: `WHERE key_prefix LIKE 'legacy%' AND is_active` + iterate + bcrypt.
- Check `_not_expired(row)` (expiry column; uses ADR-009 timestamp convention).
- Check `tenant.is_active` guard.
- Raise `HTTPException(401, detail="Invalid or missing API key")` — detail is a string, envelope rendered by I-RFC7807.
- Structlog events: `auth_success` with `path="new_format"` or `path="legacy"`; `auth_failed` with `path` and prefix (new-format only); `auth_legacy_path_used` as warning on every legacy authentication with `sunset` date bound.

### I-05 — `caller_feature` on `InvokeRequest` (`app/models/request.py`)

- Add `caller_feature: Optional[str] = Field(default=None, max_length=128)` to `InvokeRequest` between `caller_module` and `tenant_id`.
- Confirm `ConfigDict(extra="forbid")` still rejects unknown fields.
- Update OpenAPI schema export (see I-09).

### I-06 — `caller_feature` through cost pipeline

- Thread `caller_feature` from `InvokeRequest` → `app.gateway.cost_emitter.emit_cost_event_from_gateway` → `app.cost.meter.emit_cost_event` → `CostEvent` row.
- All intermediate functions accept the parameter explicitly (no kwargs opacity).
- `cost_events.caller_feature` populated exactly as sent; NULL when not provided.

### I-07 — structlog binding of `caller_feature`

- In `app/gateway/router.py`, bind `caller_feature=req.caller_feature` on `invoke_start`, `invoke_complete` (when present), `invoke_failed`, and `gateway_cost_emission_failed`.
- Confirm no log line includes the full API key (only prefix or `key_shape`).

### I-08 — Rate limiter middleware (`app/gateway/middleware/rate_limiter.py`)

- New file with the SlowAPI configuration from the rate-limiting ruling:
  - `get_tenant_id(request)` key function reading `request.state.tenant_id` (set by auth dependency before rate-limit decoration fires). Falls back to `get_remote_address` pre-auth.
  - `Limiter(key_func=get_tenant_id, enabled=settings.RATE_LIMIT_ENABLED, storage_uri=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")`.
- Add config fields to `app/config.py`:
  - `RATE_LIMIT_ENABLED: bool = False`
  - `RATE_LIMIT_INVOKE_RPM: int = 60`
  - `RATE_LIMIT_JOBS_RPM: int = 120`
- Apply `@limiter.limit(f"{settings.RATE_LIMIT_INVOKE_RPM}/minute")` to `POST /api/v1/ai/invoke`.
- Apply `@limiter.limit(f"{settings.RATE_LIMIT_JOBS_RPM}/minute")` to `GET /api/v1/ai/jobs/{job_id}`.
- **Do NOT** apply limiter to `GET /api/v1/ai/capabilities` or `GET /api/v1/ai/schemas/...`.
- On 429, handler includes `Retry-After` header and returns RFC 7807 envelope via I-RFC7807.

### I-09 — Capabilities endpoint (`GET /api/v1/ai/capabilities`)

- New route in `app/gateway/router.py` returning `CapabilitiesResponse`.
- Response is static in v1.0; hand-maintained table in code reflecting the five services and their task lists.
- No `migration_head` field (Zone 1 — intentionally excluded).
- Auth required (`verify_api_key`); no rate limit.
- `capabilities_schema_version = "1"`.
- Add `ServiceCapability`, `DeprecatedTask`, `CapabilitiesResponse` Pydantic models in `app/models/response.py`.

### I-10 — Task schemas endpoint (`GET /api/v1/ai/schemas/{service_type}/{task}`)

- New route returning `TaskSchemaResponse`.
- Use `model.model_json_schema()` for payload and result models for the named task.
- `422 /errors/unsupported-service` when `service_type` not in registry.
- `404 /errors/task-not-found` when task not registered for that service_type.
- Auth required; no rate limit.
- Maintain task → `(payload_model, result_model)` map alongside `SERVICE_MAP`.

### I-11 — 202 on async services (behavioural correction)

- In `app/gateway/router.py`, when `req.service_type in ASYNC_SERVICES`, return `JobAcceptedResponse` with `status_code=202`.
- Change in router: use `from fastapi import status` and return `JSONResponse(content=..., status_code=202)` OR declare the route with `response_class=JSONResponse` and set status on handler return.
- Document in §14 Change Log as behavioural correction from pre-governance 200.

### I-12 — Cross-tenant 404 on `GET /ai/jobs/{job_id}` (confirm existing behaviour)

- Verify current filter `WHERE job_id = ? AND tenant_id = ?` is intact.
- Add structlog event `job_not_found` with both `job_id` and authenticated `tenant_id` (server-side; NOT returned in response).

### I-13 — `X-Request-Id` response header

- On success and on error, emit `X-Request-Id` response header matching the body `request_id`.
- Set via response header write in router handler (sync path) and via exception handler (error path — read from `request.state.request_id`).
- `request_id` is generated by router at top of handler and bound to `request.state.request_id` early so the exception handler can retrieve it.

### I-RFC7807 — validation (covered above, AC-S5)

### I-ADR-030 — Register capability endpoint Zone 2 governance in ASP-ADR.md

- Append ADR-030 entry under "Locked by ASP-FEAT-ASP-00 v1.0" with the Type B/Type C change classification for capability response shape.
- Update `ASP-INDEX.md` ADR count.

### I-ADR-032 — Register rotation mechanics in ASP-ADR.md

- Append ADR-032 amendment documenting: multi-key junction table, dual-path auth during 90-day Type C window, 5-step rotation/revocation protocol, post-sunset cleanup migration as AC-Close.
- Update `ASP-INDEX.md` ADR count.

### I-ADR-034 — Register OpenAPI export on migration in ASP-ADR.md

- New ADR-034: "OpenAPI schema export on every migration."
- Rationale: canonical machine-readable record of the external contract at each migration head; enables consumer SDK generation.
- Implement `scripts/export_openapi.py` that runs `app.main.app.openapi()` and writes to `docs/openapi/asp-openapi-<migration_head>.json`.
- Add checklist item to Post-Implementation Checklist in `CLAUDE.md`: "After applying any migration, run `python scripts/export_openapi.py` and commit the snapshot."
- Append ADR-034 entry to `ASP-ADR.md`; update `ASP-INDEX.md` ADR count (033 → 034).

### I-14 — Legacy-key operator communication (PAP `pap_runner`)

- Issue a new-format key for PAP on spec acceptance.
- Communicate to PAP operator: existing `pap_runner` key remains valid until `<acceptance + 90d>`; adopt new key at leisure; signal acknowledgement when at least one request succeeds on the new prefix.
- Record communication in `asp-projects/00-index/communication/`.

### I-15 — Documentation sweep

- `CLAUDE.md` — update migration head to 023 after I-01; update applied chain; add ADR-034 checklist item.
- `ASP-SCHEMA-CURRENT.md` — document new `tenant_api_keys` table, amended `tenants` and `cost_events`, migration 023.
- `ASP-INDEX.md` — update migration head; update ADR count to 034; update Gateway status from "COMPLETE" to "GOVERNED" on AC passage; close W-5 blocker.
- `ASP-ADR.md` — append ADR-030 / ADR-032 / ADR-034 entries.
- 3-way sync to `asp-projects/00-index/`, `asp-projects/00-index/communication/`, `asp-projects/01-master/`.

### I-16 — Test suite additions

- `tests/gateway/test_auth.py` — dual-path auth (new-format success, new-format fail, legacy success, legacy fail, expired row, is_active=False tenant, revoked key).
- `tests/gateway/test_rate_limiter.py` — dormancy with `RATE_LIMIT_ENABLED=False`, enforcement with `RATE_LIMIT_ENABLED=True`, per-tenant isolation, 429 body + `Retry-After`.
- `tests/gateway/test_rfc7807.py` — every error path returns `application/problem+json` with all six envelope fields.
- `tests/gateway/test_caller_feature.py` — captured in structlog, persisted in `cost_events`, not used for routing.
- `tests/gateway/test_capabilities.py` — shape, auth required, `migration_head` absent.
- `tests/gateway/test_schemas_endpoint.py` — happy path, 422 unsupported service, 404 unknown task.
- `tests/gateway/test_async_202.py` — doc_intelligence / prediction return 202.

### I-17 — Pre-governance verification gate

- Before declaring GOVERNED, run full 35+ AC matrix (§12) against a clean environment.
- Submit AC verification report (mirroring ASP-FEAT-ASP-01-v1_2-AC-VERIFICATION.md format).
- Chief Architect signs off → status flips to GOVERNED.

### Post-acceptance / AC-Close items

- **AC-Close-01:** after T+90d, write `remove_legacy_api_key_path` migration (number allocated at that time per ADR-028). Delete legacy rows, remove dual-path branch from `auth.py`, remove `auth_legacy_path_used` event from observability inventory.
- **AC-Close-02:** after T+90d, delete pre-rotation `pap_runner` key row.
- **AC-Close-03:** governance sweep — ASP-INDEX flips from "Gateway: GOVERNED (pre-sunset)" to "Gateway: GOVERNED (single-format)".

## §12 Acceptance Criteria

**Target:** 35 ACs across the eight scope items + cross-cutting. Each AC is binary pass/fail and independently verifiable. 100% PASS required before GOVERNED.

### S-1 — Auth O(N) fix (key_prefix approach)

| AC | Statement | Verification |
|---|---|---|
| **AC-S1-01** | A new-format key `asp_<prefix12>_<secret32>` authenticates successfully in a single indexed lookup + single bcrypt check. | structlog: `auth_success path="new_format"`; DB trace shows one SELECT on `ix_tenant_api_keys_prefix`. |
| **AC-S1-02** | Auth overhead for a new-format key is ≤ 150 ms p95 in the pilot environment. | Synthetic benchmark: 100 requests, measure time from request arrival to handler invocation. |
| **AC-S1-03** | A well-formed new-format key with a prefix not present in `tenant_api_keys` returns 401 without scanning any other rows. | SQL query log shows single SELECT returning zero rows; no fallback scan. |
| **AC-S1-04** | A malformed key (not matching `^asp_[a-z0-9]{12}_[A-Za-z0-9]{32}$`) takes the legacy path, not the new-format path. | structlog: `auth_legacy_path_used`. |

### S-2 — Multi-key support (ADR-032 mechanics)

| AC | Statement | Verification |
|---|---|---|
| **AC-S2-01** | A tenant with two active `tenant_api_keys` rows authenticates successfully on either key. | Two issued keys, both authenticate; both produce `auth_success`. |
| **AC-S2-02** | Setting `is_active=FALSE` and `revoked_at=now()` on a row causes that key to fail auth (401) on the next request; other keys for the tenant continue to work. | Revoke key A; key A returns 401; key B returns 200. |
| **AC-S2-03** | The CHECK constraint `ck_tenant_api_keys_revocation_consistency` rejects an `UPDATE` that sets `is_active=FALSE` without `revoked_at`. | Direct SQL UPDATE fails with integrity error. |
| **AC-S2-04** | The CHECK constraint `ck_tenant_api_keys_expiry_order` rejects an INSERT with `expires_at <= issued_at`. | Direct SQL INSERT fails with integrity error. |
| **AC-S2-05** | A row with `expires_at < now()` fails auth with 401 even when `is_active=TRUE`. | Set `expires_at` to past; request returns 401. |
| **AC-S2-06** | `UNIQUE INDEX ix_tenant_api_keys_prefix` rejects a second row with the same `key_prefix`. | Direct SQL INSERT fails. |
| **AC-S2-07** | Deleting a tenant cascades and removes all its `tenant_api_keys` rows. | `DELETE FROM tenants WHERE id = ?`; verify no orphan rows. |
| **AC-S2-08** | Rotation 5-step protocol (§10) is documented in ASP-ADR.md ADR-032 amendment; a dry-run rotation (issue → overlap → consumer ack → revoke → audit) is completed on a non-production tenant before Gateway spec is marked GOVERNED. | Entry in ADR-032; communication artefact in `asp-projects/00-index/communication/`. |

### S-3 — Rate limiting

| AC | Statement | Verification |
|---|---|---|
| **AC-S3-01** | With `RATE_LIMIT_ENABLED=False`, 1000 sequential requests to `/ai/invoke` from the same tenant all return 200 (assuming no other failures). | Integration test; no 429s. |
| **AC-S3-02** | With `RATE_LIMIT_ENABLED=True` and `RATE_LIMIT_INVOKE_RPM=60`, the 61st request within a 60-second window returns 429 with `application/problem+json` body and `Retry-After` header. | Integration test; assert 429 + header + envelope. |
| **AC-S3-03** | Rate limiting is per-tenant: tenant A exceeding their limit does NOT affect tenant B. | Test with two tenants; A gets 429, B still 200. |
| **AC-S3-04** | With `RATE_LIMIT_ENABLED=False`, no keys are written to Redis under `slowapi:*`. | `redis-cli KEYS 'slowapi:*'` returns empty set after 100 requests. |
| **AC-S3-05** | `GET /ai/capabilities` and `GET /ai/schemas/*` are not rate-limited even when `RATE_LIMIT_ENABLED=True`. | 200 requests to each in 1 second; all return 200. |

### S-4 — ADR-034 / OpenAPI export

| AC | Statement | Verification |
|---|---|---|
| **AC-S4-01** | `python scripts/export_openapi.py` produces `docs/openapi/asp-openapi-0023.json` containing all four Gateway endpoints (E-1..E-4). | File exists; JSON contains all four paths; schema is draft-07-compatible. |
| **AC-S4-02** | The exported schema includes `caller_feature` in `InvokeRequest` with `maxLength: 128` and nullable true. | Inspect `components.schemas.InvokeRequest.properties.caller_feature`. |
| **AC-S4-03** | `CLAUDE.md` Post-Implementation Checklist includes the OpenAPI export step. | Grep `CLAUDE.md`. |

### S-5 — RFC 7807 error envelope

| AC | Statement | Verification |
|---|---|---|
| **AC-S5-01** | Every error response carries `Content-Type: application/problem+json`. | Integration test covering 400, 401, 404, 422, 429, 500 paths. |
| **AC-S5-02** | Every error response body has exactly the six top-level fields `{type, title, status, detail, instance, request_id}`. | JSON schema assertion per endpoint. |
| **AC-S5-03** | `status` in the body equals the HTTP status code. | Assertion. |
| **AC-S5-04** | `request_id` is present on post-auth error responses and matches the `X-Request-Id` response header. | Integration test. |
| **AC-S5-05** | Pre-auth 401 responses render the envelope correctly even though `request.state.request_id` is None (field is `null`, not absent). | Direct test with missing key. |
| **AC-S5-06** | A 401 body does not disclose whether the prefix was found, whether `is_active` was false, or whether expiry fired. | Body inspection for all four failure modes returns identical text. |

### S-6 — `caller_feature` field (F-01-10)

| AC | Statement | Verification |
|---|---|---|
| **AC-S6-01** | `InvokeRequest` accepts a `caller_feature` string of up to 128 chars; 129 chars returns 422. | Validation test. |
| **AC-S6-02** | `caller_feature` value sent by caller appears verbatim in the `cost_events.caller_feature` column and in structlog `invoke_start` / `invoke_complete` events. | DB query + log assertion. |
| **AC-S6-03** | Omitting `caller_feature` results in a successful request and `cost_events.caller_feature IS NULL`. | Backwards-compat test. |
| **AC-S6-04** | Observability dashboards MUST NOT flag `caller_feature IS NULL` as a data-quality issue. Analytics SHOULD group by `COALESCE(caller_feature, '<unknown>')`. | Dashboard definitions reviewed; sample analytics query committed in `scripts/sql/cost_by_feature.sql`. |
| **AC-S6-05** | `caller_feature` value has zero effect on routing (same `service_type`/`task` reaches same handler), zero effect on prompt selection, and is NOT returned in `InvokeResponse`. | Integration test: same request with and without `caller_feature` produces identical response body (modulo `request_id`). |

### S-7 — Capability endpoint governance (ADR-030)

| AC | Statement | Verification |
|---|---|---|
| **AC-S7-01** | `GET /ai/capabilities` returns 200 with a `CapabilitiesResponse` body containing all five services and their task lists for a valid API key. | Integration test. |
| **AC-S7-02** | `GET /ai/capabilities` returns 401 when `X-ASP-API-Key` is missing or invalid. | Integration test. |
| **AC-S7-03** | The response body does NOT contain a `migration_head` field. | Schema assertion. |
| **AC-S7-04** | `GET /ai/schemas/{service_type}/{task}` returns 200 with draft-07 JSON Schema for a known task; 422 for `service_type=rag`; 404 for unknown task. | Three integration tests. |
| **AC-S7-05** | ADR-030 entry in `ASP-ADR.md` documents the Type B (additive) vs Type C (removal/retype) change classification for the capabilities response shape. | Grep ADR-030. |

### S-8 — DEFECT-010 resolution (rotation SOP mechanics)

| AC | Statement | Verification |
|---|---|---|
| **AC-S8-01** | The 5-step rotation protocol (issue → overlap → consumer ack → revoke → audit) is executed end-to-end on a non-production tenant before Gateway is marked GOVERNED. | Artefact in `asp-projects/00-index/communication/`. |
| **AC-S8-02** | During the overlap window, both old and new keys authenticate; structlog distinguishes them via `path` (new_format / legacy) and prefix. | Overlap test in I-16. |
| **AC-S8-03** | After revocation, the old key returns 401 consistently across 10 consecutive requests. | Post-revoke assertion. |
| **AC-S8-04** | DEFECT-010 is marked RESOLVED in `ASP-DEFECT-REGISTER.md` with reference to this spec and AC-S8-01..03 as evidence. | Grep defect register. |

### Cross-cutting

| AC | Statement | Verification |
|---|---|---|
| **AC-X-01** | Migration 023 applies cleanly on a database at head 0022; `alembic current` reports single head 0023; downgrade to 0022 runs without error. | Migration round-trip test. |
| **AC-X-02** | The `X-Request-Id` response header is present on every success and every error, matching the body `request_id`. | Integration test per endpoint. |
| **AC-X-03** | No log line anywhere in the Gateway contains the full API key plaintext. Only prefix (for new format) or `key_shape=legacy` is logged. | Grep structured log output after full test pass. |
| **AC-X-04** | ASP-INDEX W-5 blocker ("Governance spec writing: ASP-00 Gateway") is closed in the same commit that marks Gateway GOVERNED. | Grep ASP-INDEX diff. |
| **AC-X-05** | Async services (`doc_intelligence`, `prediction`) return HTTP 202 with `JobAcceptedResponse`; sync services return HTTP 200 with `InvokeResponse`. | Integration tests for each branch. |

**Total ACs in v1.0: 36** (S-1: 4, S-2: 8, S-3: 5, S-4: 3, S-5: 6, S-6: 5, S-7: 5, S-8: 4, X: 5).

## §13 Open Questions

| OQ | Question | Owner | Target resolution |
|---|---|---|---|
| **OQ-1** | Should `GET /api/v1/ai/capabilities` response shape include `auth_methods: ["api_key"]` to prepare for future OAuth2 / mTLS support? | Chief Architect | Decide before AC verification. Default in v1.0: NO (YAGNI; reintroduce as Type B addition in a future spec). |
| **OQ-2** | Should the legacy-path 401 response include a structured hint to the caller (e.g. `"Migration to new key format recommended"`)? Would shorten operator comms but inflates `detail` and could mislead. | Chief Architect | Decide before AC verification. Default in v1.0: NO — keep `detail` opaque. |
| **OQ-3** | *Escalated out of Open Questions — see §14 Change Log pending entry.* | — | Recorded as a governance commitment in §14. |
| **OQ-4** | Should rate-limit counters emit a warning structlog event when a tenant crosses 80% of their RPM? Would help operators call out noisy-neighbour issues before they hit 429. | Chief Architect | Decide before AC verification. Default in v1.0: NO (out of scope; defer to v2.0). |
| **OQ-5** | Should `GET /ai/schemas/{service_type}/{task}` cache Pydantic-generated JSON Schemas in-process (rebuild on import only) versus regenerating per request? Pilot volume is low; correctness > perf. | ASP Dev Team | Decide during I-10 implementation. Default: in-process dict built at startup; acceptable because schemas are static between deploys. |
| **OQ-6** | Operator-facing key management endpoint (create/revoke) — confirmed deferred to a post-v1.0 spec. Reconfirm at spec acceptance. | Chief Architect | Reconfirmed in §3 out-of-scope; OQ-6 exists to record that we discussed it and deferred. |
| **OQ-7** | Should `caller_feature` be surfaced as a label on rate-limit buckets (finer-grained limits per feature)? Would enable PAP F-03-04 vs F-03-08 vs F-01-10 to have independent RPMs. | Chief Architect | Decide at v2.0 review. v1.0 default: NO — single bucket per tenant. |

## §14 Change Log

| Version | Date | Author | Notes |
|---|---|---|---|
| v1.0-draft | 2026-04-17 | ASP Development Team | Initial authoring. Eight-item scope per Chief Architect ruling. Template: ASP-GOV-PLAYBOOK-001 §5 verbatim. Migration 023 reserved. |
| v1.0 (accepted) | TBD | ASP Development Team + Chief Architect | Awaiting AC verification and Chief Architect acceptance. |

### Pending Change Log entries (to be resolved at v1.0 acceptance)

| Entry | Description | Resolution trigger |
|---|---|---|
| **PE-1 — ADR-032 Type C sunset date** | The sunset date for the ADR-032 Type C window (end of legacy key format coexistence) is a governance commitment, not an open question. It is recorded here pending confirmation of the Type C window start date with PAP. At v1.0 acceptance, this row becomes an appended Change Log entry of the form: *"ADR-032 Type C window start: YYYY-MM-DD. Sunset: YYYY-MM-DD (+90 calendar days). Legacy `auth.py` path removal tracked as AC-Close-01."* | Spec acceptance + Type C start-date confirmation with PAP. |

### Behavioural corrections from pre-governance state

These are changes from the current `app/gateway/` implementation to what v1.0 governs. They are documented here so that post-acceptance regression reviews have a clear diff.

| # | Pre-governance behaviour | v1.0 governed behaviour | Impact |
|---|---|---|---|
| BC-1 | Async services (`doc_intelligence`, `prediction`) return HTTP 200 with `JobAcceptedResponse`. | Return HTTP 202. | Non-breaking for PAP — PAP reads `job_id` from body, does not branch on 200 vs 202. Brings Gateway into alignment with HTTP semantics (202 = accepted for later processing). No consumer comms required. |
| BC-2 | Errors emit FastAPI default `{"detail": "..."}` envelope. | Errors emit RFC 7807 envelope `{type, title, status, detail, instance, request_id}` at top level with `Content-Type: application/problem+json`. | Type B additive (existing `detail` semantics preserved; new fields added). PAP's existing error handler continues to work unchanged. |
| BC-3 | Auth iterates all active tenants with bcrypt (O(N)). | Auth does O(1) prefix lookup + single bcrypt; legacy O(N) path retained for the 90-day Type C window. | Performance win; no caller-visible behaviour change during the window. |
| BC-4 | `tenants.api_key_hash` is the single source of truth for API keys. | `tenant_api_keys` junction table is the source of truth; `tenants.api_key_hash` dropped. | Schema change; backfill preserves every active tenant's existing key during the window. |
| BC-5 | Prior to v1.0, PAP was required to pass `caller_feature` inside `payload{}` (treated as an opaque dict) to avoid 422 rejection on `InvokeRequest`. | v1.0 promotes `caller_feature` to a first-class `Optional[str]` field on `InvokeRequest`. The 422 rejection surface for unknown top-level fields (`ConfigDict(extra="forbid")`) is preserved — `caller_feature` is now explicitly declared and accepted. | Fixes the F-01-10 observability gap observed on req `d7633490` (2026-04-16) and closes the open question of where that field was smuggled pre-v1.0. |
| BC-6 | `cost_events` has no feature dimension. | `cost_events.caller_feature` column added. | Enables cost-by-feature analytics. |

### ADR deltas locked by v1.0

- **ADR-030** — capabilities endpoint Zone 2 governance; Type B/Type C change rules codified.
- **ADR-032** — multi-key rotation mechanics locked; 5-step protocol; 90-day Type C window.
- **ADR-034** (new) — OpenAPI schema export on every migration; added to `CLAUDE.md` Post-Implementation Checklist.

### Deferred to future specs / TSCDs

See §3 (out of scope) and §13 (open questions). Not a change log entry in their own right but linked here for traceability.

---

**End of Batch 3 (§11–§14). All 14 sections drafted. 36 ACs total. RFC 7807 global exception handler sketch included in §11 I-RFC7807. Awaiting Chief Architect review of Batch 3 before v1.0-draft is sealed and .docx conversion begins.**
