# ASP-SCHEMA-CURRENT — Database Schema Reference

## Migration Head
**Current:** `0025` (seed_suggest_screen_mapping_prompt — PAP-ASP-REQ-ASP-01 v2.0 / BP-10 prompt-only)

## Tables

### tenants
Stores API client configuration. API keys moved to `tenant_api_keys` in 0023.
- Created in: 0001
- Amended in: 0023 (dropped `api_key_hash` column; authoritative key source is `tenant_api_keys`)

### tenant_api_keys
Multi-key junction table per tenant. Supports rotation with overlap windows, revocation audit, optional expiry. ADR-032 mechanics locked by ASP-FEAT-ASP-00 v1.0.
- Created in: 0023
- Columns: `id, tenant_id (FK CASCADE), key_prefix VARCHAR(12) UNIQUE, api_key_hash VARCHAR(255), issued_at, expires_at NULL, revoked_at NULL, is_active, label NULL, created_at, updated_at`
- Indexes: `ix_tenant_api_keys_prefix` (UNIQUE), `ix_tenant_api_keys_tenant` (tenant_id, is_active)
- CHECK: `ck_tenant_api_keys_revocation_consistency`, `ck_tenant_api_keys_expiry_order`
- Backfill: legacy rows have `key_prefix` = `'leg_' || substr(tenant_id::text, 1, 8)`; matched in auth via `func.left(key_prefix, 4) == 'leg_'` (deterministic, no LIKE wildcard)

### prompt_templates
Prompt templates for all AI services with variant support.
- Created in: 0001
- Seeded in: 0002 (base services), 0003 (test cases inferred+snapshot), 0004 (Playwright TS POM), 0005 (Playwright Python pytest)
- Modified in: 0012 (TC ID naming rule), 0013 (flat script variants), 0014 (analyse_failure), 0015 (OUTPUT CONTRACT)
- Reconstituted in: 0016 (with_inventory from serene-shtern archive, ASP-NOTE-004)
- Seeded in: 0017 (classify_probe_result for ASP-01 NLP)

### cost_events
Per-call cost tracking records.
- Created in: 0001
- Amended in: 0023 (added `caller_feature VARCHAR(128) NULL` + `ix_cost_events_caller_feature` — F-01-10 governance. NULL means pre-feature or non-PAP caller, NOT a data quality issue.)

### async_jobs
Tracks Celery async job status for Doc Intelligence and Prediction services.
- Created in: 0001

### webhook_registrations
Per-tenant webhook configuration for event delivery.
- Created in: 0001

### cost_monthly_reports
Aggregated monthly cost rollups (idempotent).
- Created in: 0001

## Non-Postgres Persistence (ChromaDB)

ASP-02 RAG + ASP-12 Ontology Manager persist schema chunks in ChromaDB. Governed by ASP-FEAT-ASP-02 v1.0 (joint, 2026-04-20 under ASP-NOTE-011). **No Alembic migration** — ChromaDB state lives on the `chroma_data` Docker volume mounted at `/chroma/data` on both `ai-service` and `celery-worker` (AC-S1-03 verified).

- **Collection naming:** `asp_schema_{tenant_id}` (primary tenant isolation).
- **Collection metadata:** `{"hnsw:space": "cosine", "asp_embedding_model": <settings.RAG_EMBEDDING_MODEL>}` — EF model snapshot for drift detection (warn-only per AC-S3-02; ADR-035 DEFERRED).
- **Chunk metadata contract** (`app.schemas.rag_schemas.ChunkMetadata`, `extra="forbid"` — ASP-OUT-024 §5 ruling): `table_name`, `module`, `tenant_id`, `chunk_type: Literal["schema","example"]`.
- **tenant_id defence-in-depth:** every `retrieve()` `where=` clause includes `{"tenant_id": {"$eq": tenant_id}}` regardless of `exclude_tables` state (§10.1 Layer 2 / AC-S5-01..03).
- **Client:** `chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)` with a 5-minute TTL singleton (`CHROMA_CLIENT_TTL_SECONDS=300`) for cross-process visibility.
- **Embedding function:** `SentenceTransformerEmbeddingFunction(model_name=settings.RAG_EMBEDDING_MODEL)` — pre-downloaded at Dockerfile build time (AC-S2-04); bound explicitly at both ingest and query.

## Migration Chain
| ID | Description | Notes |
|----|-------------|-------|
| 0001 | Initial schema — all core tables | Baseline |
| 0002 | Seed prompt templates for base services | |
| 0003 | Generate test cases prompt templates (inferred + snapshot) | |
| 0004 | Generate Playwright TypeScript POM script prompt | |
| 0005 | Playwright Python/pytest prompt variant | |
| 0012 | TC ID naming rule for inventory prompt | down_revision healed 0011→0005 (ASP-NOTE-004) |
| 0013 | Flat script generation prompts (TS + Python) | Cherry-picked from serene-shtern |
| 0014 | analyse_failure prompt for playwright_runner | Cherry-picked from serene-shtern |
| 0015 | OUTPUT CONTRACT append to test-case prompts | Cherry-picked from serene-shtern |
| 0016 | Reconstitute with_inventory prompt from archive | ASP-NOTE-004 Phase 2 |
| 0017 | Seed classify_probe_result prompt (NLP, PAP canonical) | Renumbered from 0006 |
| 0018 | Ban lambda in Python Playwright script prompts | ASP-FEAT-ASP-03 v1.1 / DEFECT-006 |
| 0019 | Update generate_test_cases_with_inventory prompt to v2 (dual-mode: F-03-08 + F-03-04) | ASP-TSCD-001 CHG-03 |
| 0020 | Redesign with_inventory prompt v3 — simplified schema, F-03-04/F-03-08 modes | OPS-003 resolution |
| 0021 | Elevate count enforcement to system prompt (Rule 3 hard-constraint) | Superseded by 0022 |
| 0022 | Neutral Rule 3 — count enforcement moved to handler post-processing | Principal Architect ruling |
| 0023 | Create `tenant_api_keys` junction; backfill legacy rows; drop `tenants.api_key_hash`; add `cost_events.caller_feature` | ASP-FEAT-ASP-00 v1.0 Gateway governance |
| 0024 | ASP-FEAT-ASP-03 v2.0 — prompt-only: deactivate v3 + v1-L2; insert v4 playwright_runner + v4 test_generator (split by caller); seed refactor_script_locators v1 | ASP-FEAT-ASP-03 v2.0 (GOVERNED) |
| 0025 | Seed `suggest_screen_mapping` v1 prompt row (nlp / test_generator / * / v1 / NULL) | PAP-ASP-REQ-ASP-01 v2.0 / BP-10 (ASP-OUT-020) |
| 0026 | Seed three generation prompt rows: `draft_steps`, `suggest_preconditions`, `propose_edge_cases` (generation / test_generator / * / v1 / NULL) | F-03-02 / PAP-ASP-REQ-ASP-02 v1.0 (ASP-OUT-036) |
| 0027 | Seed `extract_test_entities` v1 prompt row (nlp / test_generator / * / v1 / NULL) | F-03-02 / PAP-ASP-REQ-ASP-02 v1.0 (ASP-OUT-036) |

## Last Updated
2026-04-21 — Migrations 0026 + 0027 applied (prompt-only seeds for F-03-02). Migration head 0027. No DDL changes; four new prompt rows total across `generation` (3) and `nlp` (1) services.
