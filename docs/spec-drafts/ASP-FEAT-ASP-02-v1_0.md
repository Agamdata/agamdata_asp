# ASP-FEAT-ASP-02 v1.0 — RAG Service + Ontology Manager Detailed Spec

**Status:** DRAFT — Batch 1 (§1–§5) surfaced for Architect review
**Template:** ASP-GOV-PLAYBOOK-001 v1.0, Section 5 (14-section template, verbatim)
**Scope:** Jointly governs ASP-02 RAG Service AND ASP-12 Ontology Manager in a single spec cycle (per architecture-diagram ruling, 2026-04-18)
**Migration head at authoring:** 0025
**Migrations allocated by this spec:** **None.** No Postgres schema changes. All work is config + code + ChromaDB.
**Implementation state:** Stream B fixes already shipped (I-RAG-01 through I-RAG-04) — commits `a15e3fc`, `b4fbce9`, `40ff092`, `7538fb9`. This spec governs the fixed state + remaining net-new items (S-4, S-5, S-6).
**Drafted by:** ASP Development Team (Claude)
**Date:** 2026-04-18
**Reviewer:** Principal Architect & Engineer

---

## §1 Summary

**ASP-02 RAG Service** and **ASP-12 Ontology Manager** are governed together in one spec cycle. RAG is a **Zone 1 internal service** — not gateway-exposed, not consumer-callable. The only caller is **ASP-01 NLP via the `nl_to_sql` handler**. RAG makes **no LLM calls**; it only performs vector retrieval against ChromaDB using sentence-transformers embeddings. ASP-12 Ontology Manager is the **write path** (admin-triggered via Celery, populates collections from PostgreSQL schema metadata); ASP-02 RAG is the **read path** (called from NLP's `nl_to_sql` step to retrieve relevant schema chunks for LLM context). Both share ChromaDB state via a persistent volume mount; they are otherwise independent code paths. The spec formalises the previously-broken production path (PAP `nl_to_sql` never worked end-to-end in pilot until I-RAG-01/02/03/04 shipped) and governs three net-new items: a Pydantic `ChunkMetadata` model, defence-in-depth tenant scoping in retrieval filters, and a fail-closed policy on empty collection.

## §2 Background and Context

**Why this spec exists.** ASP-02 and ASP-12 have been in-codebase since project inception but have never been governed. The pre-spec codebase survey (2026-04-18) identified ten gaps (G-1 through G-10) across persistence, embedding consistency, metadata contract, sync scheduling, security, and reachability. Four of those gaps had been silently blocking the `nl_to_sql` production path — no tenant in this pilot had ever completed an `nl_to_sql` call with meaningful retrieval behind it.

**Phase.** Part of the foundational governance sweep alongside ASP-00 (Gateway, GOVERNED 2026-04-18) and ASP-03 (Generation, GOVERNED v2.0 2026-04-18). ASP-01 NLP was GOVERNED at v1.2 (2026-04-10) before any of these — its `nl_to_sql` handler was governed against an assumed-working RAG layer; this spec finally brings RAG up to the same governance standard so the NLP contract can be trusted end-to-end.

**Historical drivers (survey-numbered gaps).**

| Gap | Finding | Shipped fix (if any) |
|---|---|---|
| **G-1** | Ephemeral `chromadb.Client()` — no persistence path; wiped on every container restart | **I-RAG-01** (`a15e3fc`): `PersistentClient(path=/chroma/data)` + named volume mount |
| **G-2** | Celery-worker container ran without `./app:/app/app` bind mount — silent code-drift from ai-service during development | fixed collaterally in I-RAG-01 docker-compose rewrite |
| **G-3** | Implicit ONNX embedding + docstring claimed `sentence-transformers/all-MiniLM-L6-v2` that was never actually installed; ONNX cache never populated (retrieval has literally never executed in pilot history) | **I-RAG-02** (`b4fbce9`): explicit `SentenceTransformerEmbeddingFunction` bound at both `get_collection` and `get_or_create_collection`; model pre-downloaded at Dockerfile build; `asp_embedding_model` snapshot + drift-warning helper |
| **G-4** | Ontology sync Celery task existed but was never scheduled | **I-RAG-03** (`40ff092`): `ontology-sync-daily` beat_schedule entry at 02:00 UTC; cron-path no-op safe for the pilot phase |
| **G-5** | No defence-in-depth `tenant_id` filter in `where=` clause — relies entirely on collection-name scoping | **NOT YET SHIPPED — S-5 below** |
| **G-6** | No fail-closed policy on empty / missing collection — NLP silently invokes LLM with empty schema_context, risking hallucination | **NOT YET SHIPPED — S-6 below** |
| **G-7** | `chroma_client` singleton held cache across cross-container writes; celery-worker upserts invisible to ai-service reader | **I-RAG-02** (`b4fbce9`): `CHROMA_CLIENT_TTL_SECONDS=300` (OQ-RAG-CACHE-01 Option B ruling) |
| **G-8** | Beat scheduler not actually running (`--concurrency=4` without `-B`) — `monthly-cost-aggregation` and `ontology-sync-daily` both dead code | **I-RAG-04** (`7538fb9`): docker-compose command `-B` flag added |
| **G-9** | Metadata contract for ChromaDB chunks was docstring-only — no Pydantic enforcement, silent drift risk | **NOT YET SHIPPED — S-4 below** |
| **G-10** | Pre-spec survey surfaced that `get_prompt_variant` strict-exact behaviour would break any future prompt-templates migration at `maturity="*"` | spurious to RAG; resolved via ASP-OUT-014 Option A fallback chain in the Generation v2.0 cycle |

**Adjacent governance reference.** ADR-001 (Zone 1 services internal-only), ADR-004 (`exclude_tables` RAG-layer enforcement — this spec preserves ADR-004 and adds defence-in-depth `tenant_id` alongside it), ADR-034 (OpenAPI snapshot per migration — **N/A here** because there are no migrations in this spec), ASP-DEFECT-021 (`alembic/env.py` fix — unrelated but surfaced during I-RAG-01).

**What depends on this spec's GOVERNED state.**

- ASP-01 NLP `nl_to_sql` task reliability — currently operates against an un-governed RAG; once ASP-02 is GOVERNED, the NLP contract (§7 in ASP-FEAT-ASP-01 v1.2) is fully backed.
- Future per-tenant prompt schema synchronisation (PAP has expressed interest in this for downstream LogiCRM integration — will be a separate spec cycle, not v1.0).
- Atrium transition — this spec cleanly separates runtime (read) from admin (write), which is the shape Atrium will require.

## §3 Scope

### In scope — seven items

| # | Scope item | State | Source |
|---|---|---|---|
| **S-1** | `PersistentClient(path=/chroma/data)` + Docker named volume shared across ai-service and celery-worker | **COMPLETE** | I-RAG-01 · commit `a15e3fc` |
| **S-2** | Explicit `SentenceTransformerEmbeddingFunction` binding at both retrieve and upsert call sites; model pre-downloaded at Dockerfile build | **COMPLETE** | I-RAG-02 · commit `b4fbce9` |
| **S-3** | Collection metadata snapshot (`asp_embedding_model` field) + drift-warning helper `_check_embedding_model_snapshot` | **COMPLETE** | I-RAG-02 · commit `b4fbce9` |
| **S-4** | **NEW — Pydantic `ChunkMetadata` model** for chunk shape enforcement | **NOT YET SHIPPED** | this spec |
| **S-5** | **NEW — Defence-in-depth `tenant_id` filter** inside `retrieve()`'s `where=` clause | **NOT YET SHIPPED** | this spec |
| **S-6** | **NEW — Fail-closed policy on empty collection** — `retrieve()` returns a structured signal (or NLP handler treats it as 503) rather than empty `schema_context` | **NOT YET SHIPPED** | this spec |
| **S-7** | Celery beat schedule for `run_ontology_sync` (02:00 UTC daily) + `-B` flag on celery-worker | **COMPLETE** | I-RAG-03 + I-RAG-04 · commits `40ff092` + `7538fb9` |

### Out of scope (explicitly deferred)

- **HTTP client migration** (`chromadb.HttpClient()` in place of `PersistentClient`) — Atrium-era concern. PersistentClient with volume is fit for pilot. Deferred to a future TSCD when multi-worker or distributed Chroma becomes required.
- **Per-tenant embedding model overrides** — current model is global via `settings.RAG_EMBEDDING_MODEL`. Per-tenant overrides would require a `tenants.rag_embedding_model` column and a re-index policy on tenant mutation. Deferred.
- **ChromaDB collection versioning** — collection metadata already carries `asp_embedding_model` + `hnsw:space`. A full version-bump convention (e.g. migrate from `asp_schema_<tenant>` → `asp_schema_v2_<tenant>` on embedding-model change) is deferred; warn-only on mismatch for v1.0 per OQ-RAG-CACHE-01 pattern.
- **RAG as a gateway-exposed service** — RAG is intentionally Zone 1 per ADR-001. The capabilities endpoint already excludes it (verified by AC-CC in ASP-FEAT-ASP-00 v1.0). Keeping it Zone 1 is a governed non-goal of v1.0.
- **ADR-035 (fail-closed on embedding-model mismatch)** — proposed during pre-spec survey; now explicitly deferred. S-6 governs fail-closed on empty collection (different, narrower property). A stricter policy for embedding-model mismatch at collection-open time is a future ADR.

### Joint-governance rationale (ASP-02 + ASP-12 in one cycle)

Ontology Manager (ASP-12) and RAG (ASP-02) have been separate services by ID but are operationally a single contract: Ontology Manager writes chunks with a specific metadata shape; RAG reads those chunks assuming the same shape. Separating them into two spec cycles would mean governing half of a contract in each cycle, with the metadata schema either duplicated or cross-referenced. Joint governance keeps the metadata contract (S-4) in one spec, under one set of ACs, with one migration path. The two services remain distinct in dispatch (ASP-02 is called from NLP; ASP-12 runs via Celery beat) — only the governance surface is shared.

## §4 Service Classification

| Attribute | ASP-02 RAG | ASP-12 Ontology Manager |
|---|---|---|
| **Zone** | Zone 1 (internal) | Zone 1 (internal) |
| **External API surface** | None | None |
| **Gateway-exposed** | No | No |
| **In `/api/v1/ai/capabilities`** | No (intentional; AC-CC-02 in v1.0 governs this exclusion) | No |
| **LLM calls** | **None** — vector retrieval only | **None** — schema metadata → ChromaDB upsert only |
| **Model** | N/A | N/A |
| **Embedding function** | `SentenceTransformerEmbeddingFunction(model_name=settings.RAG_EMBEDDING_MODEL)` | Same (shared) |
| **Callers** | `app.services.nlp._handle_nl_to_sql` only | Celery beat (scheduled) + operator manual trigger |
| **Sync / async** | Sync (Python coroutine — handler awaits `rag.retrieve(...)`) | Async (Celery task); runs out-of-process |
| **Datastore** | ChromaDB (`/chroma/data` persistent volume) | ChromaDB (shared with RAG) + PostgreSQL read access (schema introspection in future extensions; no writes) |
| **Postgres tables owned** | None | None |
| **Config owned** | `CHROMA_PERSIST_PATH`, `RAG_EMBEDDING_MODEL`, `CHROMA_CLIENT_TTL_SECONDS` (all three shipped in Stream B) | None additional — uses `DATABASE_URL` for Postgres schema introspection (future) |
| **Celery schedule** | N/A (sync) | `ontology-sync-daily` at `crontab(hour=2, minute=0)` UTC (shipped in I-RAG-03; runs with `-B` per I-RAG-04) |
| **Observability events** | `rag_chroma_client_initialised` (with TTL + reason), `rag_embedding_function_initialised`, `rag_embedding_model_mismatch`, `rag_chunks_upserted`, `rag_collection_not_found`, `rag_collection_create_failed` | `ontology_sync_scheduled_trigger` (cron no-op), `ontology_sync_started`, `ontology_sync_complete` (future: per-tenant breakdown) |

**Latency budget.** RAG `retrieve()` is wall-clock-bounded by ChromaDB query time (target: p95 < 100 ms for a 50-chunk collection; pilot-scale). No network I/O for embeddings (local sentence-transformers). First call in a process has a ~1.5 s warm-up penalty for embedding-function init — amortised over process lifetime.

**Failure domains.**

- ChromaDB unavailable (volume unmounted or corrupt): `retrieve()` returns empty → currently NLP hallucinates; S-6 governs this.
- Embedding model mismatch on open: warn-only today; ADR-035 (deferred) will govern fail-closed.
- Cross-tenant leak via collection-name bug: collection name is `asp_schema_<tenant_id>` and is the only enforcement today; S-5 governs the defence-in-depth layer.

## §5 Data Model

### Migrations required: **NONE**

This spec adds **zero Postgres migrations**. All state lives in ChromaDB (filesystem volume) plus three configuration settings (already shipped). No Alembic operation is required. Pre-write gate G-5 is therefore **N/A**; G-PROMPT-REACH is **N/A** (no prompt registry involvement).

### Configuration additions (shipped in Stream B)

Located in `app/config.py`:

```python
CHROMA_PERSIST_PATH: str = "/chroma/data"
RAG_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_CLIENT_TTL_SECONDS: int = 300
```

`CHROMA_PERSIST_PATH` also mirrored as an env var on both `ai-service` and `celery-worker` in `docker-compose.yml`, with the named volume `chroma_data:/chroma/data` mounted identically on both — so `_chroma_client` singleton in each container sees the same on-disk SQLite + HNSW index files.

### ChromaDB collection shape

| Property | Value |
|---|---|
| **Naming convention** | `asp_schema_{tenant_id}` — one collection per tenant |
| **Distance metric** | `cosine` |
| **Embedding function binding** | `SentenceTransformerEmbeddingFunction(model_name=settings.RAG_EMBEDDING_MODEL)` — explicit, not default; bound at both `get_collection()` (retrieve path) and `get_or_create_collection()` (upsert path) |
| **Collection metadata** (stored via `metadata={...}` at `get_or_create_collection`) | `{"hnsw:space": "cosine", "asp_embedding_model": settings.RAG_EMBEDDING_MODEL}` |
| **Drift detection** | `_check_embedding_model_snapshot(collection)` — warns on mismatch between `metadata["asp_embedding_model"]` and `settings.RAG_EMBEDDING_MODEL` (warn-only today; ADR-035 deferred) |

### Chunk metadata contract (S-4 — net-new Pydantic model)

Currently docstring-only. v1.0 governs a Pydantic model to enforce the shape at ingest:

```python
# app/schemas/rag_schemas.py (NEW FILE — S-4)

from typing import Literal
from pydantic import BaseModel, ConfigDict


class ChunkMetadata(BaseModel):
    """Metadata stored alongside every ChromaDB chunk.

    Enforced at ingest via app.ontology.manager.build_schema_chunk() and
    any future upserter. Consumers (RAG retrieve path) rely on the shape
    for filtering — ADR-004 `exclude_tables` filter keys on `table_name`;
    S-5 defence-in-depth tenant filter keys on `tenant_id`.
    """
    model_config = ConfigDict(extra="forbid")

    table_name: str                                       # ADR-004 filter key
    module: str                                           # caller module (e.g. "PAP", "LogiCRM")
    tenant_id: str                                        # S-5 defence-in-depth filter key
    chunk_type: Literal["schema", "example"]              # governed taxonomy
```

`extra="forbid"` — unknown fields in a chunk's metadata dict must fail loudly at ingest, preventing silent drift.

### Retrieve filter — `where=` clause (S-5 — defence-in-depth tenant scoping)

Current code (shipped in I-RAG-02):

```python
# app/services/rag.py — retrieve()  (current — S-5 NOT yet applied)
where = None
if exclude_tables:
    where = {"table_name": {"$nin": exclude_tables}}
```

Governed (S-5) — always include `tenant_id` in the filter alongside the collection-name scoping:

```python
# Governed v1.0 — S-5 defence-in-depth
where = {"tenant_id": tenant_id}
if exclude_tables:
    where = {"$and": [
        {"tenant_id": tenant_id},
        {"table_name": {"$nin": exclude_tables}},
    ]}
```

Two layers of tenant isolation (collection name + metadata filter) — either alone is sufficient, both together is defence-in-depth. Any future collection-name bug (e.g. mistyped prefix) still can't leak cross-tenant data because the metadata filter still applies.

### Empty-collection policy (S-6 — fail-closed)

Current behaviour: if a tenant's collection doesn't exist OR returns zero chunks, `retrieve()` returns `[]`; NLP then calls the LLM with empty `schema_context` and typically gets hallucinated table names.

Governed v1.0 — **fail-closed** policy:

```python
# app/services/rag.py — retrieve()  (governed behaviour, S-6)
try:
    collection = client.get_collection(collection_name, embedding_function=_get_embedding_function())
except Exception:
    log.error("rag_collection_not_found", tenant_id=tenant_id, collection=collection_name,
              remediation="tenant has no ontology; run admin ontology_sync before nl_to_sql")
    raise RAGCollectionMissingError(tenant_id=tenant_id)
```

NLP's `_handle_nl_to_sql` catches `RAGCollectionMissingError` and raises `HTTPException(503)` — a caller-visible, clear error rather than an LLM hallucination. New exception class `RAGCollectionMissingError` added to `app/services/rag.py`.

### Unchanged elements

- `asp_schema_{tenant_id}` naming convention
- `cosine` distance
- `exclude_tables` `$nin` semantics (ADR-004 preserved)
- Ontology manager chunk construction (`app/ontology/manager.py` — unchanged)
- Celery beat schedule (I-RAG-03/I-RAG-04 shipped as-is)
- `CHROMA_CLIENT_TTL_SECONDS=300` (OQ-RAG-CACHE-01 Option B shipped)

### Pre-write gate (all gates N/A or inherited)

| Gate | Status | Notes |
|---|---|---|
| **G-1 Schema** | **N/A** | No Postgres tables |
| **G-2 Types** | **N/A** | No Postgres columns |
| **G-3 Contract** | Pending — §6/§7 in Batch 2 | Internal Python contract; no HTTP surface |
| **G-4 Audit (CHECK)** | **N/A** | No Postgres constraints |
| **G-5 Migration** | **N/A** | No Alembic migration — migration head remains 0025 |
| **G-6 Frontend** | **N/A** | No UI |
| **G-7 Dependency** | Pending — after §§6–10 | New module `app/schemas/rag_schemas.py` (S-4); new exception class in `rag.py` (S-6) — import-check at Batch 3 I-RAG-06 |
| **G-8 Prompt Reach** | **N/A** | No prompt registry usage |

---

**End of Batch 1 (§1–§5).** Awaiting Architect review before Batch 2 (§6 API Contract · §7 Request/Response Detail · §8 Caller Integration · §9 LLM and Prompt Design · §10 Security Requirements).
