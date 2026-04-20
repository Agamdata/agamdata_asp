# ASP-INDEX

Last updated: 2026-04-20 | Migration head: 025 | Phase: ASP-02 RAG + ASP-12 Ontology Manager governance closure (ASP-NOTE-011) | 5/14 services GOVERNED

## ASP-INDEX Maintenance Protocol (ADR-026 — BINDING)

**Owner:** ASP Development Team maintains this file in the repo.
**Reviewers:** Chief Architect reviews at every deployment.

### Who updates ASP-INDEX

| Role | Responsibility |
|---|---|
| Chief Architect / Product | Authors specs, rulings, ASP-NOTEs, TSCDs, governance documents. Shares deliverables with ASP Development Team. |
| ASP Development Team | Receives deliverables and updates ASP-INDEX.md in the repo. This is part of the implementation — not a separate task. |
| Chief Architect | Reviews ASP-INDEX at every deployment. Flags gaps between architect records and repo state. |

### When ASP-INDEX must be updated

| Trigger | What to update | Deadline |
|---|---|---|
| Migration applied | Migration head, applied chain table, ASP-SCHEMA-CURRENT.md | Same PR as the migration |
| Service status change | Service status table (e.g. ACTIVE → IN SPEC → GOVERNED) | Same PR as the status-changing work |
| New spec version delivered | Spec doc column in service status table | Within 1 business day of receiving the spec |
| TSCD issued | TSCD register table | Within 1 business day |
| ASP-NOTE issued | ASP-NOTE register table + inline note content | Within 1 business day |
| New ADR locked | Locked decisions list | Same PR as the implementing code |
| New consumer onboarded | Consumer register + caller integration req register | Same PR as tenant provisioning |
| New governance document approved | Governance documents table | Within 1 business day |
| Caller integration requirement received | Caller integration requirements table | Within 1 business day |

### Deployment review checklist (Chief Architect)

At every deployment, the Chief Architect verifies:

1. **Migration head** in ASP-INDEX matches `alembic current` in the deployed environment.
2. **Service status** reflects reality — no service marked GOVERNED without a closure ASP-NOTE.
3. **ADR list** includes every ADR referenced in any active spec.
4. **TSCD register** includes every issued TSCD — no orphaned amendments.
5. **ASP-NOTE register** includes every issued note.
6. **Consumer register** lists every active consumer with correct caller_module values.

If a gap is found: Chief Architect raises it with the ASP Development Team lead. The gap is corrected before the next deployment proceeds. Repeated gaps are escalated to Product Owner.

### Rule: ASP-INDEX is a single canonical file

- Updated in-place. No version suffix. No `ASP-INDEX-v1_37.md`.
- `Last updated` header timestamp updated on every edit.
- Git history is the version trail.

## What to upload for each task type

| Task | Upload these files |
|---|---|
| New service spec | ASP-INDEX.md + ASP-SCHEMA-CURRENT.md |
| Service spec review / TSCD | ASP-INDEX.md + ASP-SCHEMA-CURRENT.md + spec under review |
| Migration writing | ASP-INDEX.md + ASP-SCHEMA-CURRENT.md |
| Bug / gap investigation | ASP-INDEX.md + ASP-SCHEMA-CURRENT.md + relevant service spec |
| Caller integration requirement | ASP-INDEX.md + ASP-SCHEMA-CURRENT.md + ASP-GOV-CONSUMPTION-002 |

## Current migration head

**024 — v4_prompts_coverage_form_live_extracted_refactor** (ASP-FEAT-ASP-03 v2.0 in-draft — prompt-only; deactivates v3 + v1-L2 inventory rows; inserts v4 playwright_runner + v4 test_generator (split-by-caller); seeds `refactor_script_locators` v1)

Applied chain: 001 → 002 → 003 → 004 → 005 → 012 → 013 → 014 → 015 → 016 → 017 → 018 → 019 → 020 → 021 → 022

| Migration | Description | Feature |
|---|---|---|
| 001 | initial_schema — all 6 tables created | Baseline |
| 002 | seed_nl_to_sql_prompts | Pre-governance (existing) |
| 003 | seed_generate_test_cases_prompts (inferred + snapshot) | Pre-governance (existing) |
| 004 | seed_generate_playwright_script (TypeScript POM) | Pre-governance (existing) |
| 005 | seed_playwright_python_pytest variant | Pre-governance (existing) |
| 012 | tc_id_naming_prompt (down_revision healed 0011→0005, ASP-NOTE-004) | Pre-governance (recovered) |
| 013 | flat_script_prompts (TypeScript + Python flat variants) | Pre-governance (recovered) |
| 014 | analyse_failure_prompt (playwright_runner) | Pre-governance (recovered) |
| 015 | output_contract (OUTPUT CONTRACT append to test-case prompts) | Pre-governance (recovered) |
| 016 | reconstitute_generation_prompts (with_inventory from volume archive c52be9c) | ASP-NOTE-004 Phase 2 |
| 017 | seed_classify_probe_result_prompt (renumbered from 006) | ASP-FEAT-ASP-01 v1.2 |
| 018 | ban_lambda_in_playwright_python (patch Python script prompt) | ASP-FEAT-ASP-03 v1.1 / DEFECT-006 |
| 019 | update_generation_with_inventory_prompt_v2 (dual-mode F-03-08/F-03-04, VARIANT B INSERT at *) | ASP-TSCD-001 CHG-03 |

No pending migrations. Chain is linear. Single head: 022.

### Note on migration gap (006-011)
Migrations 006-011 were never committed to git. They existed only in the serene-shtern Docker volume. Production prompt state was recovered via Phase 1 archive (c52be9c) and reconstituted into migration 016. 0012's down_revision was healed from '0011' to '0005'. See ASP-NOTE-004.

### Note on migration convention
ASP uses sequential numeric revision strings: '001', '002', '003'. Same convention as PAP.
Never use hex UUIDs as revision IDs. `down_revision` must always be verified against `alembic current` before writing.

### Note on migration history correction
Migrations 002–005 were active in the codebase but untracked in ASP-INDEX prior to ASP-FEAT-ASP-01 v1.2. Corrected during governance onboarding. See ASP-NOTE-002.

## Locked decisions (ADRs)

- **ADR-001:** All external modules call ASP-00 Gateway only. No direct calls to internal services (ASP-01 through ASP-13) from outside the platform.
- **ADR-002:** ASP is stateless per call. Conversation history is owned and managed by the calling module. ASP-07 Context Store is a convenience cache, not the source of truth.
- **ADR-003:** ASP is built as a standalone microservice with REST API — not an internal Python package. Language independence, independent deployability, clean module separation.
- **ADR-004:** `schema_hints.exclude_tables` is enforced at RAG retrieval layer (ChromaDB metadata filter) BEFORE chunks are passed to the LLM. A prompt instruction alone is insufficient.
- **ADR-005:** All prompt templates stored in `prompt_templates` table. No prompts hardcoded in application code. PromptNotFoundError raised when no template is found.
- **ADR-006:** ASP-08 Cost Meter must never raise an exception — wrap all writes in try/except and log only. A failed cost log must NOT fail the user request.
- **ADR-007:** ASP-10 Cost Aggregator must be idempotent — `INSERT ... ON CONFLICT DO UPDATE`. Running twice for the same month produces the same result.
- **ADR-008:** All Pydantic models use `ConfigDict(extra="forbid")` to reject unknown fields. Prevents modules from accidentally passing undocumented keys.
- **ADR-009:** All timestamps are `TIMESTAMPTZ` (UTC). Never `TIMESTAMP WITHOUT TIME ZONE`.
- **ADR-010:** `structlog` throughout. Never `print()`. Every log entry must include `request_id`, `tenant_id`, `caller_module` where available.
- **ADR-011:** Stack traces must never be returned to the client. Log internally, return `{"detail":"Internal error","request_id":"..."}` externally. RFC 7807 Problem Detail format.
- **ADR-012:** API keys stored as bcrypt hashes. Never plaintext, never logged. (As of ASP-FEAT-ASP-00 v1.0, authoritative storage is `tenant_api_keys.api_key_hash`; `tenants.api_key_hash` was dropped in migration 023 in favour of the multi-key junction table per ADR-032.)
- **ADR-013:** S3/MinIO file keys must be prefixed with `{tenant_id}/` to prevent cross-tenant file access.
- **ADR-014:** Context Store Redis keys scoped to `ctx:{tenant_id}:{caller_module}:{session_id}`. Cross-tenant reads are impossible by key design.
- **ADR-015:** Webhook callbacks must be signed with HMAC-SHA256 when a secret is registered. Receiving module must verify the signature.
- **ADR-016:** `ANTHROPIC_API_KEY` must only be read from environment. Never log it, never include in any response.
- **ADR-017:** `quality_tier` (standard/enhanced/premium) maps to model names via ASP-11 Model Router. Modules never specify model names directly. Mapping: standard=claude-haiku-4-5-20251001, enhanced=claude-sonnet-4-6, premium=claude-opus-4-6.
- **ADR-018:** ECS Fargate (not Lambda) for API runtime. LLM calls can take 2–10 seconds, exceeding Lambda timeouts.
- **ADR-019:** ASP-13 Dashboard Intelligence: screenshot mode for PoC, serialised chart data for production. ASP-13 accepts both `input_mode` values and routes internally.
- **ADR-020:** DQE (Dynamic Query Engine) build approach — Option A (Cube.dev integration) vs Option B (custom build) — **OPEN DECISION**. Requires product owner ruling before implementation sprint begins.
- **ADR-021:** Caller integration requirements use `{CALLER}-ASP-REQ-{SERVICE-ID}` naming. Consumer-owned documents. ASP reviews and implements. Established in PAP-ASP-REQ-ASP-01 v1.0, formalised in ASP-GOV-CONSUMPTION-002 v1.0.
- **ADR-022:** Three-zone ownership boundary model. Zone 1 (ASP Platform) — ASP-owned, no consumer visibility. Zone 2 (Shared Contract) — jointly governed, cross-consumer review required. Zone 3 (Consumer-Owned) — consumer's domain, ASP implements to contract. Formalised in ASP-GOV-CONSUMPTION-002 v1.0.
- **ADR-023:** Change classification: Type A (consumer-isolated, no notification), Type B (additive, 5-business-day review), Type C (breaking, 90-day deprecation, explicit consumer acknowledgement). Formalised in ASP-GOV-CONSUMPTION-002 v1.0.
- **ADR-024:** Pydantic schemas in `app/schemas/`, ORM models in `app/models/`. Clean separation. Applies to all ASP services. Locked during ASP-FEAT-ASP-01 v1.2 dev team review.
- **ADR-025:** Cross-cutting LLM utilities (JSON parsing, prompt building) in `app/utils/`. Shared across services. Not duplicated per service module. `extract_json()` lives in `app/utils/json_parser.py`. Locked during ASP-FEAT-ASP-01 v1.2 dev team review.
- **ADR-026:** ASP-INDEX.md is maintained by the ASP Development Team in the repo. Chief Architect reviews at every deployment. Specs, rulings, and notes flow from Architect → Dev Team → ASP-INDEX. Gaps found at deployment review are corrected before next deployment. See Maintenance Protocol section above.
- **ADR-026.1 (Addendum):** Living governance documents have an authoritative repo location and a coordination working copy. Both must be updated in the same operation. Working copy is the location used for Chief Architect review and consumer coordination; repo is the location used for production deployment and CI. Working copy refresh is performed automatically by the ASP Development Team after migration completes. Applies to: ASP-INDEX.md, ASP-SCHEMA-CURRENT.md, ASP-ADR.md, ASP-DEFECT-REGISTER.md, and any future living governance document.
- **ADR-027:** All prompt templates MUST be seeded via committed Alembic migrations. Production DB state is never a source of truth for prompts. Volume-only or manually-inserted prompts are Critical defects. Strengthens ADR-005. (ASP-NOTE-004)
- **ADR-028:** Pre-writing migrations for unimplemented tasks (aspirational OUTPUT CONTRACTs, schema stubs) is forbidden. A migration in the chain is executed reality, not planned work. (ASP-NOTE-004)
- **ADR-029:** Every PR that touches the migration chain must verify `alembic upgrade head` succeeds on a fresh empty DB and `alembic heads` returns exactly one head. CI gate. No exceptions. (ASP-NOTE-004)
- **ADR-030:** `GET /api/v1/ai/capabilities` and `GET /api/v1/ai/schemas/{service_type}/{task}` are Zone 2 Shared Contract surfaces. Every authenticated consumer is entitled to query supported tasks and Pydantic payload schemas at runtime. Consumers should validate at startup (ASP-GOV-CONSUMPTION-002 best practice). Amended by ASP-FEAT-ASP-00 v1.0: auth required on both endpoints; `migration_head` intentionally excluded (Zone 1 operational); additive changes Type B, removals/retypes Type C.
- **ADR-031:** Phantom task resurrection requires formal caller integration requirement.
- **ADR-026.2 (Addendum):** Living governance documents may have more than two locations. The authoritative repo location and any coordination working copies (currently `00-index/` and `00-index/communication/`, plus any future targets) must all be updated in the same operation. The ASP Development Team maintains the canonical list of sync targets in ENGINEERING-PLAYBOOK.md and adds new targets to that list before the first sync to them. A "synced" claim is only valid when every listed target has been updated and verified identical (checksum or diff). (ASP-NOTE-005)
- **ADR-032:** API key rotation requires (1) advance written notification to all affected consumers, (2) overlap window where both old and new keys are valid for minimum 5 business days, (3) explicit consumer acknowledgement before old key is revoked. **ACCEPTED** — code mechanics locked by ASP-FEAT-ASP-00 v1.0: `tenant_api_keys` junction table (migration 023), new key format `asp_<prefix12>_<secret32>` (49 chars), dual-path `verify_api_key` during 90-day Type C window, 5-step rotation protocol (issue → overlap → consumer ack → revoke → audit), post-sunset cleanup migration as AC-Close. (ASP-DEFECT-010)
- **ADR-033:** Per-service Pydantic strictness — generation service payload models (`GenerateTestCasesPayload`, `GenerateTestCasesWithInventoryPayload`, `LocatorInventoryItem`, `LocatorInventoryLocators`) use `ConfigDict(extra="ignore")` as a documented exception to ADR-008. All other services retain `extra="forbid"`. INFO log emitted on every dropped field for observability. Locked during ASP-FEAT-ASP-03 v1.1 dev team review. (ASP-DEFECT-009)
- **ADR-034:** OpenAPI schema export artifact on every migration. ASP exports an OpenAPI 3.x JSON snapshot at each migration apply, stored at `docs/openapi/asp-openapi-<migration_head>.json`, consumed by PAP CI for contract drift detection. Step added to `CLAUDE.md` Post-Implementation Checklist. Locked by ASP-FEAT-ASP-00 v1.0.

## Service status

| ID | Name | Type | Status | Spec Doc | TSCDs |
|---|---|---|---|---|---|
| ASP-00 | Gateway | Synchronous | **GOVERNED** | ASP-FEAT-ASP-00 v1.0 | — |
| ASP-01 | NLP Service | Synchronous | **GOVERNED** | ASP-FEAT-ASP-01 v1.2 + BP-10 additive (ASP-NOTE-010) | — |
| ASP-02 | RAG Service | Synchronous | **GOVERNED** | ASP-FEAT-ASP-02 v1.0 | — |
| ASP-03 | Generation Service | Synchronous | **GOVERNED v2.0** | ASP-FEAT-ASP-03 v2.0 | TSCD-001, v2.0 amendment |
| ASP-04 | Doc Intelligence | Asynchronous | ACTIVE (pre-governance) | — | — |
| ASP-05 | Prediction Service | Asynchronous | ACTIVE (pre-governance) | — | — |
| ASP-06 | Prompt Registry | Infrastructure | ACTIVE (pre-governance) | — | — |
| ASP-07 | Context Store | Infrastructure | ACTIVE (pre-governance) | — | — |
| ASP-08 | Cost Meter | Infrastructure | ACTIVE (pre-governance) | — | — |
| ASP-09 | Webhook Service | Infrastructure | ACTIVE (pre-governance) | — | — |
| ASP-10 | Cost Aggregator | Cron/Scheduled | ACTIVE (pre-governance) | — | — |
| ASP-11 | Model Router | Infrastructure | ACTIVE (pre-governance) | — | — |
| ASP-12 | Schema Ontology Mgr | Admin triggered | **GOVERNED** | ASP-FEAT-ASP-02 v1.0 (joint with ASP-02) | — |
| ASP-13 | Dashboard Intelligence | Synchronous | ACTIVE (pre-governance) | — | — |

### Service status definitions
- **ACTIVE (pre-governance):** Built and functional. Governance spec not yet written. No TSCD trail.
- **IN SPEC:** Governance spec being drafted.
- **SPEC APPROVED:** Spec written, ASP team review complete, TSCDs resolved.
- **GOVERNED:** Spec approved + acceptance criteria verified against live service. 25/25 ACs PASS.

## Caller Integration Requirements

| Req ID | Caller | Target Service | Task | Status | Spec Doc |
|---|---|---|---|---|---|
| PAP-ASP-REQ-ASP-01 | PAP | ASP-01 NLP | classify_probe_result | IMPLEMENTED — 25/25 ACs PASS | PAP-ASP-REQ-ASP-01 v1.0 |
| PAP-ASP-REQ-ASP-03 | PAP | ASP-03 Generation | generate_test_cases, generate_test_cases_with_inventory | ACCEPTED — v1.1 implemented via ASP-TSCD-001 | PAP-ASP-REQ-ASP-03 v1.1 |
| PAP-ASP-REQ-ASP-00 | PAP | ASP-00 Gateway | (auth/keys, capabilities, error specificity) | INBOUND — filing in parallel with ASP-FEAT-ASP-00 v1.0 drafting | TBD |

## Consumer Register

| Consumer | caller_module Values | Onboarded | Integration Requirements |
|---|---|---|---|
| LogiCRM | crm, payroll, finance, hr | 2026 (pre-governance) | Pending — to be submitted during governance onboarding |
| PAP | playwright_runner, ci_pipeline | 2026 (pre-governance) | PAP-ASP-REQ-ASP-01 v1.0 (ASP-01 NLP) |

## TSCD Register

| TSCD | Amends | Issues | Status |
|---|---|---|---|
| ASP-TSCD-001 | ASP-FEAT-ASP-03 v1.1 | CHG-01..06: missing_locators formal, LocatorInventoryLocators schema, prompt v2 (dual-mode), max_tokens=8192, page_type/screen_key added. Migration 019. | IMPLEMENTED | 2026-04-15 |

Next TSCD: ASP-TSCD-002

## Open blockers

*(No open blockers. W-5 closed — ASP-00 Gateway reached GOVERNED per ASP-NOTE-008 on 2026-04-18.)*

### Recently closed (archive)

- ~~**ADR-020 DQE Option A vs B.**~~ LogiCRM scope, not ASP-owned. Removed from ASP blockers. Tracking moves to LogiCRM governance docs.
- ~~**ADR-032 mechanics.**~~ RESOLVED — API key rotation code mechanics (multi-key, overlap window, key management endpoint) folded into ASP-FEAT-ASP-00 v1.0 spec scope (W-5). No longer a standalone blocker.
- ~~**Migration 001 formalisation.**~~ RESOLVED — migration chain 001–022 confirmed and tracked. Corrected during ASP-01 governance closure; superseded by ASP-NOTE-004/005.
- ~~**Pilot vs production environment.**~~ CLOSED — "production" in PAP context = ASP pilot environment; no separate production environment exists. Clarified during pilot setup (tenant key creation 2026-04-16).
- ~~**F-01-10 unregistered caller_feature.**~~ Not an open blocker — logged as an open question for PAP-ASP-REQ-ASP-03 v2.0 spec review. Tracked under Task 2 (migration 023 coverage-aware generation) pending PAP confirmations.

## ASP-NOTE Register

| Note | Subject | Status | Date |
|---|---|---|---|
| ASP-NOTE-001 | ASP governance onboarding — foundation package created | INFORMATIONAL | 2026-04-10 |
| ASP-NOTE-002 | ASP-01 NLP Service — governance closure. 25/25 ACs PASS. First service GOVERNED. | CLOSURE | 2026-04-10 |
| ASP-NOTE-003 | ASP-INDEX maintenance protocol established. ADR-026 locked. Dev team owns repo updates; Chief Architect reviews at deployment. | PROCESS | 2026-04-10 |
| ASP-NOTE-004 | Contract drift + migration branch conflict — Phase 1/2 complete, deployed 580dbe1. CLOSED by ASP-NOTE-005. | CLOSED | 2026-04-10 |
| ASP-NOTE-005 | ASP-03 governance closure + ASP-NOTE-004 closeout. 32/32 AC PASS. AC-Close-01(b) confirmed by PAP (commit 1b32600). 2/14 GOVERNED. ADR-026.2 locked. | CLOSURE | 2026-04-12 |
| ASP-NOTE-006 | TSCD-001 completion. Migration 019, 11/11 AC PASS, 58/58 regression. DEFECT-012 MITIGATED, DEFECT-013 RESOLVED. Two production deployment gates tracked. | PROCESS | 2026-04-15 |
| ASP-NOTE-008 | ASP-00 Gateway governance closure. 36/36 AC PASS. Migration 023. ADR-030 amended, ADR-032 QUEUED→ACCEPTED, ADR-034 new. DEFECT-010/021 RESOLVED. 3/14 GOVERNED. PE-1 Type C sunset pending. | CLOSURE | 2026-04-18 |
| ASP-NOTE-009 | ASP-03 v2.0 governance closure. 37/37 AC PASS. Migration 024. Coverage-aware generation + form_data + locator_source=live_extracted + F-01-10 third caller + refactor_script_locators. ASP-DEFECT-022 filed (cost aggregator, separate task). ASP-OUT-014 regression caught + fixed (get_prompt_variant 4-level fallback). G-PROMPT-REACH gate added to playbook. | CLOSURE | 2026-04-18 |
| ASP-NOTE-010 | ASP-01 NLP — suggest_screen_mapping task added (BP-10 / PAP-ASP-REQ-ASP-01 v2.0). 8/8 AC PASS. Migration 025 (prompt-only). Type B additive. Hallucination guard verified. ASP-OUT-003 closed. | CLOSURE | 2026-04-18 |
| ASP-NOTE-011 | ASP-02 RAG + ASP-12 Ontology Manager joint governance closure. 26/26 AC PASS. No new Alembic migration (ChromaDB config only). S-4/S-5/S-6 net-new shipped: ChunkMetadata Pydantic (extra="forbid"), tenant_id defence-in-depth in where=, RAGCollectionMissingError→503 fail-closed path. Stream B commits a15e3fc..223543c resolved G-1..G-10 gap matrix. ADR-004 defence-in-depth posture formalised. 6/14 GOVERNED. | CLOSURE | 2026-04-20 |

### ASP-NOTE-002 — ASP-01 Governance Closure

**Service:** ASP-01 NLP Service
**Spec:** ASP-FEAT-ASP-01 v1.2
**Companion:** PAP-ASP-REQ-ASP-01 v1.0 (caller integration requirement)
**AC Result:** 25/25 PASS
**Migration:** 006 applied (prompt template seed for classify_probe_result)

**Governance trail:**
- v1.0: Initial detailed implementation spec (24 ACs)
- v1.1: Cross-reference against PAP-ASP-REQ-ASP-01 resolved 3 findings (F-1, F-2, F-3). AC count → 25.
- v1.2: ASP Development Team review resolved 7 findings (D-1, D-2, D-3, M-1, M-2, M-3, M-4). Two new ADRs locked (024, 025). Migration head corrected (001 → 005 → 006).
- M-1 errata: v1.2 incorrectly changed API key header to `X-Api-Key`. Reverted to `X-ASP-API-Key` — codebase canonical. No code change. Rename would be Type C breaking change per ASP-GOV-CONSUMPTION-002.

**Verification gates passed:**
- I-08: ConfigDict(extra='forbid') — all 10 schemas ✅
- I-09: Cost Meter try/except — lines 37-62 in meter.py ✅
- I-10: exclude_tables at RAG layer — ChromaDB metadata filter ✅
- I-11: structlog everywhere — request_id/tenant_id/caller_module ✅
- Gate 7: Import check — all modules import clean ✅

**Status:** ASP-01 → **GOVERNED**

**Issued by:** Chief Architect
**Date:** 2026-04-10

### ASP-NOTE-008 — ASP-00 Gateway Governance Closure

**Service:** ASP-00 Gateway
**Spec:** ASP-FEAT-ASP-00 v1.0
**AC Result:** 36/36 PASS

**Commit chain:** `3bef047` → `fb46fc7` → `1e1cea1` → `028131b` → `ecaa1ce`

**Migration:** 023 applied. Head: 0023.

**ADRs locked:**
- ADR-030 (ACCEPTED; amended — auth required on `/capabilities` and `/schemas/*`; `migration_head` excluded as Zone 1; Type B/C rules for response shape)
- ADR-032 (QUEUED → ACCEPTED; code mechanics: `tenant_api_keys` junction, `asp_<prefix12>_<secret32>` 49-char format, dual-path `verify_api_key`, 5-step rotation protocol)
- ADR-034 (new, ACCEPTED; OpenAPI schema export artefact per migration at `docs/openapi/asp-openapi-<migration_head>.json`)

**Defects resolved:**
- ASP-DEFECT-010 (multi-key support + rotation SOP mechanics)
- ASP-DEFECT-021 (`alembic/env.py` `load_dotenv(override=True)` defeats shell-level DATABASE_URL overrides; fixed to `override=False`)

**Verification harnesses:**
- `tests/phase3_gate.py` — 14/14 PASS (dual-path auth, caller_feature, 202/404/X-Request-Id)
- `tests/phase4_gate.py` — 11/11 PASS (rate limiter, capabilities, schemas)
- `tests/test_gateway.py` — 16/16 PASS (AC-S2 rotation mechanics, AC-S4 OpenAPI, AC-CC cross-cutting)

**Status:** ASP-00 → **GOVERNED**

**PE-1:** Type C window open. Sunset date pending Product Leadership confirmation. Single-touch edit to `app/gateway/auth.py` replaces the `_ADR032_SUNSET_PLACEHOLDER = "PE-1-pending"` value when the date is set.

**Issued by:** Principal Architect, ASP
**Date:** 2026-04-18

### ASP-NOTE-011 — ASP-02 RAG + ASP-12 Ontology Manager Governance Closure (joint)

**Services:** ASP-02 RAG Service, ASP-12 Schema Ontology Manager (joint governance)
**Spec:** ASP-FEAT-ASP-02 v1.0
**AC Result:** 26/26 PASS (9 phases: S-1 Persistence 4, S-2 EF 4, S-3 Metadata 2, S-4 ChunkMetadata 3, S-5 Tenant defence 3, S-6 Fail-closed 3, S-7 Beat 3, ADR-004 2, Cross-cutting 2)

**Commit chain (Stream B):** `a15e3fc` (I-RAG-01) → `b4fbce9` (I-RAG-02) → `40ff092` (I-RAG-03) → `7538fb9` (I-RAG-04) → `5cebcbf` (I-RAG-05) → `81e07dd` (I-RAG-06) → `223543c` (I-RAG-07) → `baf5a78` (I-RAG-08)

**Migration:** None. Head remains **0025**. ASP-02 / ASP-12 are ChromaDB-backed — no Postgres schema changes. Dockerfile + docker-compose changes + `app/services/rag.py` + `app/schemas/rag_schemas.py` + `app/ontology/manager.py` + `app/worker.py` beat schedule are the governance surface.

**Three net-new implementation items shipped in v1.0 cycle:**
- S-4: `ChunkMetadata` Pydantic model with `extra="forbid"` at `app/schemas/rag_schemas.py` — validated loudly at upsert (write-time boundary rule, §8.2), warned at retrieve (preserves fail-open).
- S-5: `tenant_id` defence-in-depth in ChromaDB `where=` clause — collection-name scoping is primary layer, `$eq` metadata filter is governed second belt (§10.1).
- S-6: `RAGCollectionMissingError` → NLP `HTTPException(503)` RFC 7807 envelope fail-closed path, distinct from fail-open empty-retrieve (§6.4 / §8.2).

**Gap matrix G-1..G-10 resolution:** all resolved or scoped in §14 change log.

**ADRs:**
- ADR-001 (Zone 1 classification) reaffirmed via §6.1 verbatim permanence statement.
- ADR-004 (exclude_tables enforcement at RAG metadata layer) defence-in-depth posture formalised — primary mechanism is the $nin metadata filter; NLP prompt `{exclude_tables}` placeholder is defence-in-depth only (§10.4 verbatim statement).
- ADR-035 (fail-closed on EF model mismatch) — **DEFERRED** per §13 OQ-1. Warn-only in v1.0.

**Defects resolved in cycle:**
- ASP-DEFECT-022 (cost aggregator psycopg2 absent from requirements.txt) — RESOLVED via asyncpg port with per-invocation `create_async_engine()` pattern (`d158221`). Locked by AC-S7-02 (monthly-cost-aggregation beat entry must remain present).

**Verification harness:** `tests/test_rag_v1.py` — 26/26 PASS. Stop-on-first-failure discipline enforced. Ran inside `ai-service` container via `docker compose exec` + host-side `docker inspect` for AC-S1-03 volume mount verification.

**Status:** ASP-02 → **GOVERNED**, ASP-12 → **GOVERNED**. Governed count: **5/14**.

**Issued by:** Principal Architect, ASP
**Date:** 2026-04-20

## Governance Documents

| Document ID | Title | Version | Status | Date |
|---|---|---|---|---|
| ASP-GOV-PLAYBOOK-001 | ASP Governance Playbook | v1.0 | APPROVED — BINDING | 2026-04-10 |
| ASP-GOV-CONSUMPTION-002 | Consumer Governance Agreement | v1.0 | APPROVED — BINDING | 2026-04-10 |
| ASP-FEAT-ASP-01 | NLP Service Detailed Spec | v1.2 | GOVERNED | 2026-04-10 |
| ASP-FEAT-ASP-03 | Generation Service Detailed Spec | v1.0 | SUPERSEDED by v1.1 | 2026-04-11 |
| ASP-FEAT-ASP-03 | Generation Service Detailed Spec | v1.1 | GOVERNED — 32/32 AC PASS (e8e3896), PAP confirmed (1b32600) | 2026-04-12 |
| ASP-FEAT-ASP-00 | Gateway Service Detailed Spec | v1.0 | **GOVERNED** — 36/36 AC PASS (ecaa1ce). Migration 023 applied. ADR-030/032/034 locked. DEFECT-010/021 RESOLVED. ASP-NOTE-008 issued 2026-04-18. | 2026-04-18 |
| ASP-FEAT-ASP-03 | Generation Service Detailed Spec (amendment) | v2.0 | **GOVERNED** — 37/37 AC PASS. Migration 024 applied (prompt-only: 2 v4 rows split by caller + refactor_script_locators v1). Coverage-aware generation + form_data + locator_source=live_extracted + F-01-10 third caller + refactor_script_locators new task. ASP-NOTE-009 issued 2026-04-18. ASP-DEFECT-022 filed (cost aggregator psycopg2; separate maintenance task). | 2026-04-18 |
| ASP-FEAT-ASP-02 | RAG Service + Schema Ontology Manager Detailed Spec (joint) | v1.0 | **GOVERNED** — 26/26 AC PASS (baf5a78). No migration (ChromaDB-only). S-4 ChunkMetadata + S-5 tenant_id defence-in-depth + S-6 RAGCollectionMissingError→503 shipped. ASP-NOTE-011 issued 2026-04-20. ASP-DEFECT-022 locked by AC-S7-02. | 2026-04-20 |

## Naming quick-ref

```
Tables:         snake_case plural (tenants, cost_events, async_jobs)
PKs:            id (UUID) — ASP convention differs from PAP. PAP uses {entity}_id. ASP uses id.
FKs:            {table}_{column}_fkey or descriptive name
Indexes:        idx_{table}_{purpose} (existing convention — do not change)
API prefix:     /api/v1/ai/{resource}
API key header: X-ASP-API-Key (canonical — do not rename without Type C process)
Request ID:     UUID generated per call. Included in every log entry and response.
Service keys:   ASP-00 through ASP-13
TSCD naming:    ASP-TSCD-{seq}-v{major}_{minor}
Spec naming:    ASP-FEAT-ASP-{seq}-v{major}_{minor}
Caller req:     {CALLER}-ASP-REQ-{SERVICE-ID}-v{major}_{minor}  (ADR-021)
Schemas:        app/schemas/{service}_schemas.py  (ADR-024)
ORM models:     app/models/{entity}.py
Shared utils:   app/utils/{module}.py  (ADR-025)
```
