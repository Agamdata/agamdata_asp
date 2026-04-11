# ASP-ADR — Architectural Decision Records

Source: ASP-INDEX.md (Chief Architect). This file mirrors the Locked Decisions section.

## ADR Index

| ID | Decision | Status |
|----|----------|--------|
| ADR-001 | Gateway-only external access | ACCEPTED |
| ADR-002 | Stateless per call — caller owns history | ACCEPTED |
| ADR-003 | Standalone microservice with REST API | ACCEPTED |
| ADR-004 | exclude_tables at RAG metadata filter layer | ACCEPTED |
| ADR-005 | Prompts in DB (prompt_templates), never hardcoded | ACCEPTED |
| ADR-006 | Cost Meter never raises — try/except, log only | ACCEPTED |
| ADR-007 | Cost Aggregator idempotent (ON CONFLICT DO UPDATE) | ACCEPTED |
| ADR-008 | ConfigDict(extra='forbid') on all Pydantic models | ACCEPTED |
| ADR-009 | All timestamps TIMESTAMPTZ (UTC) | ACCEPTED |
| ADR-010 | structlog with request_id, tenant_id, caller_module | ACCEPTED |
| ADR-011 | No stack traces to client — RFC 7807 | ACCEPTED |
| ADR-012 | API keys bcrypt-hashed, never plaintext/logged | ACCEPTED |
| ADR-013 | S3/MinIO keys prefixed with tenant_id | ACCEPTED |
| ADR-014 | Context Store Redis keys scoped by tenant/module/session | ACCEPTED |
| ADR-015 | Webhook HMAC-SHA256 signing | ACCEPTED |
| ADR-016 | ANTHROPIC_API_KEY from environment only | ACCEPTED |
| ADR-017 | quality_tier → model name via Model Router | ACCEPTED |
| ADR-018 | ECS Fargate (not Lambda) for API runtime | ACCEPTED |
| ADR-019 | Dashboard Intelligence: screenshot + serialised modes | ACCEPTED |
| ADR-020 | DQE build approach (Cube.dev vs custom) | **OPEN** |
| ADR-021 | Caller req naming: {CALLER}-ASP-REQ-{SERVICE-ID} | ACCEPTED |
| ADR-022 | Three-zone ownership boundary model | ACCEPTED |
| ADR-023 | Change classification: Type A/B/C | ACCEPTED |
| ADR-024 | Pydantic schemas in app/schemas/, ORM in app/models/ | ACCEPTED |
| ADR-025 | Shared utils in app/utils/ (extract_json etc.) | ACCEPTED |
| ADR-026 | ASP-INDEX maintenance protocol | ACCEPTED |
| ADR-026.1 | Dual-location governance docs (repo + working copy, same operation) | ACCEPTED |
| ADR-027 | All prompts via committed Alembic migrations (ADR-005 enforcement) | ACCEPTED |
| ADR-028 | Migrations = executed reality, not planned work | ACCEPTED |
| ADR-029 | Fresh-DB alembic upgrade head must pass before any PR merges | ACCEPTED |
| ADR-030 | Capability discovery endpoint (Zone 2 Shared Contract) | ACCEPTED |

---

## Full ADR Records

### ADR-001: Gateway-Only External Access
All external modules call ASP-00 Gateway only. No direct calls to internal services (ASP-01 through ASP-13) from outside the platform.

### ADR-002: Stateless Per Call
ASP is stateless per call. Conversation history is owned and managed by the calling module. ASP-07 Context Store is a convenience cache, not the source of truth.

### ADR-003: Standalone Microservice
ASP is built as a standalone microservice with REST API — not an internal Python package. Language independence, independent deployability, clean module separation.

### ADR-004: exclude_tables at RAG Layer
`schema_hints.exclude_tables` is enforced at RAG retrieval layer (ChromaDB metadata filter) BEFORE chunks are passed to the LLM. A prompt instruction alone is insufficient.

### ADR-005: Prompts in Database
All prompt templates stored in `prompt_templates` table. No prompts hardcoded in application code. PromptNotFoundError raised when no template is found.

### ADR-006: Cost Meter Resilience
ASP-08 Cost Meter must never raise an exception — wrap all writes in try/except and log only. A failed cost log must NOT fail the user request.

### ADR-007: Cost Aggregator Idempotency
ASP-10 Cost Aggregator must be idempotent — `INSERT ... ON CONFLICT DO UPDATE`. Running twice for the same month produces the same result.

### ADR-008: ConfigDict(extra='forbid')
All Pydantic models use `ConfigDict(extra="forbid")` to reject unknown fields. Prevents modules from accidentally passing undocumented keys.

### ADR-009: TIMESTAMPTZ Always
All timestamps are `TIMESTAMPTZ` (UTC). Never `TIMESTAMP WITHOUT TIME ZONE`.

### ADR-010: Structured Logging
`structlog` throughout. Never `print()`. Every log entry must include `request_id`, `tenant_id`, `caller_module` where available.

### ADR-011: No Stack Traces to Client
Stack traces must never be returned to the client. Log internally, return `{"detail":"Internal error","request_id":"..."}` externally. RFC 7807 Problem Detail format.

### ADR-012: API Keys Bcrypt-Hashed
API keys stored as bcrypt hashes in `tenants.api_key_hash`. Never plaintext, never logged.

### ADR-013: Tenant-Scoped S3 Keys
S3/MinIO file keys must be prefixed with `{tenant_id}/` to prevent cross-tenant file access.

### ADR-014: Tenant-Scoped Context Store
Context Store Redis keys scoped to `ctx:{tenant_id}:{caller_module}:{session_id}`. Cross-tenant reads are impossible by key design.

### ADR-015: Webhook HMAC-SHA256 Signing
Webhook callbacks must be signed with HMAC-SHA256 when a secret is registered. Receiving module must verify the signature.

### ADR-016: API Key from Environment Only
`ANTHROPIC_API_KEY` must only be read from environment. Never log it, never include in any response.

### ADR-017: Model Routing Abstraction
`quality_tier` (standard/enhanced/premium) maps to model names via ASP-11 Model Router. Modules never specify model names directly. Mapping: standard=claude-haiku-4-5-20251001, enhanced=claude-sonnet-4-6, premium=claude-opus-4-6.

### ADR-018: ECS Fargate Runtime
ECS Fargate (not Lambda) for API runtime. LLM calls can take 2-10 seconds, exceeding Lambda timeouts.

### ADR-019: Dashboard Intelligence Modes
ASP-13 Dashboard Intelligence: screenshot mode for PoC, serialised chart data for production. ASP-13 accepts both `input_mode` values and routes internally.

### ADR-020: DQE Build Approach — OPEN
DQE (Dynamic Query Engine) build approach — Option A (Cube.dev integration) vs Option B (custom build) — **OPEN DECISION**. Requires product owner ruling before implementation sprint begins.

### ADR-021: Caller Integration Requirement Naming
Caller integration requirements use `{CALLER}-ASP-REQ-{SERVICE-ID}` naming. Consumer-owned documents. ASP reviews and implements. Established in PAP-ASP-REQ-ASP-01 v1.0, formalised in ASP-GOV-CONSUMPTION-002 v1.0.

### ADR-022: Three-Zone Ownership Boundary
Zone 1 (ASP Platform) — ASP-owned, no consumer visibility. Zone 2 (Shared Contract) — jointly governed, cross-consumer review required. Zone 3 (Consumer-Owned) — consumer's domain, ASP implements to contract. Formalised in ASP-GOV-CONSUMPTION-002 v1.0.

### ADR-023: Change Classification
Type A (consumer-isolated, no notification), Type B (additive, 5-business-day review), Type C (breaking, 90-day deprecation, explicit consumer acknowledgement). Formalised in ASP-GOV-CONSUMPTION-002 v1.0.

### ADR-024: Schema/Model Separation
Pydantic schemas in `app/schemas/`, ORM models in `app/models/`. Clean separation. Applies to all ASP services. Locked during ASP-FEAT-ASP-01 v1.2 dev team review.

### ADR-025: Shared Utilities
Cross-cutting LLM utilities (JSON parsing, prompt building) in `app/utils/`. Shared across services. Not duplicated per service module. `extract_json()` lives in `app/utils/json_parser.py`. Locked during ASP-FEAT-ASP-01 v1.2 dev team review.

### ADR-026: ASP-INDEX Maintenance Protocol
ASP-INDEX.md is maintained by the ASP Development Team in the repo. Chief Architect reviews at every deployment. Specs, rulings, and notes flow from Architect → Dev Team → ASP-INDEX. Gaps found at deployment review are corrected before next deployment.

### ADR-026.1: Dual-Location Governance Documents (Addendum to ADR-026)
**Context:** ASP-INDEX.md and other living governance docs exist in two locations: the repo (authoritative, used for deployment/CI) and a working copy (used for Chief Architect review and consumer coordination). Drift between the two causes confusion.
**Decision:** Both locations must be updated in the same operation. Working copy refresh is performed automatically by the ASP Development Team after every migration completes. Applies to: ASP-INDEX.md, ASP-SCHEMA-CURRENT.md, ASP-ADR.md, ASP-DEFECT-REGISTER.md, and any future living governance document.

### ADR-027: All Prompts Via Committed Migrations
**Context:** ASP-NOTE-004 root cause — migrations 0006-0011 were never committed. Prompts lived only in Docker volume.
**Decision:** All prompt templates MUST be seeded via committed Alembic migrations. Production DB state is never a source of truth for prompts. Volume-only or manually-inserted prompts are Critical defects. Strengthens ADR-005.

### ADR-028: Migrations = Executed Reality
**Context:** ASP-NOTE-004 — migration 0016 (deep_dive OUTPUT CONTRACT) referenced a task that never existed.
**Decision:** Pre-writing migrations for unimplemented tasks (aspirational OUTPUT CONTRACTs, schema stubs) is forbidden. A migration in the chain is executed reality, not planned work.

### ADR-029: Fresh-DB Upgrade Gate
**Context:** ASP-NOTE-004 — the 0006-0011 gap would have been caught immediately by a CI check.
**Decision:** Every PR that touches the migration chain must verify `alembic upgrade head` succeeds on a fresh empty DB and `alembic heads` returns exactly one head. CI gate. No exceptions.

### ADR-030: Capability Discovery Endpoint
**Context:** PAP called tasks that did not exist, with no runtime way to verify.
**Decision:** `GET /api/v1/ai/capabilities` is a Zone 2 Shared Contract surface. Every consumer is entitled to query supported tasks and schemas at runtime. Consumers should validate at startup (ASP-GOV-CONSUMPTION-002 best practice).

## Last Updated
2026-04-11
