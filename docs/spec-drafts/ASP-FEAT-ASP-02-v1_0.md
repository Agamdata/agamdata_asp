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
    # Zone 1 internal — extra="forbid" intentional. Drift between ASP-12
    # write contract and ASP-02 read contract must fail loudly. (Comment
    # added per ASP-OUT-024 §5 ChunkMetadata ruling.)
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

**End of Batch 1 (§1–§5).** Batch 2 follows.

---

## §6 API Contract

RAG and Ontology Manager expose **two internal Python surfaces only** — **no external HTTP endpoints**. Both services are explicitly excluded from the Gateway and the capabilities surface per Zone 1 classification (ADR-001).

### §6.1 Governed capabilities-exclusion decision

`rag` and `ontology_manager` are **not** present in `GET /api/v1/ai/capabilities` and must remain absent. This is verified by AC-CC-02 in ASP-FEAT-ASP-00 v1.0 (the capabilities response enumerates `nlp`, `generation`, `doc_intelligence`, `prediction`, `dashboard_intelligence` only).

**Governed statement (this spec, ASP-OUT-024 §6 ruling):**

> *The absence of RAG from `GET /api/v1/ai/capabilities` is correct and permanent per ADR-001. Any future TSCD proposing gateway exposure of RAG requires a Zone reclassification ADR before it can proceed.*

This language is binding. A future TSCD or ADR that attempts to expose RAG externally must:
1. Cite this paragraph.
2. Produce a Zone reclassification ADR (Zone 1 → Zone 2 or Zone 3) as a prerequisite.
3. Separately re-spec tenant isolation, auth, cost emission, rate limiting — none of which are currently wired for RAG because RAG is internal.

### §6.2 RAG read-path contract (ASP-02)

```python
# app/services/rag.py  (module-scoped public surface)

async def retrieve(
    query: str,
    tenant_id: str,
    top_k: int = 5,
    exclude_tables: Optional[list[str]] = None,
) -> list[ChunkResult]:
    """Retrieve top-k relevant chunks for an NLP query.

    Raises RAGCollectionMissingError if the tenant has no ontology
    seeded (S-6 fail-closed).

    Applies the ADR-004 exclude_tables filter (primary enforcement)
    AND the S-5 defence-in-depth tenant_id filter in the ChromaDB
    `where=` clause.
    """


def format_chunks(chunks: list[ChunkResult]) -> str:
    """Convert retrieval results to a string suitable for LLM prompt
    injection as `{schema_context}`. See §7.2 for format details.
    Returns "" for an empty list (distinct from RAGCollectionMissingError).
    """
```

### §6.3 Ontology-manager write-path contract (ASP-12)

```python
# app/ontology/manager.py

async def upsert_chunks(
    tenant_id: str,
    chunks: list[ChunkCandidate],
) -> int:
    """Idempotent upsert of chunks into `asp_schema_{tenant_id}`.
    ChunkCandidate → ChunkMetadata validated at boundary; extra=forbid
    rejection of unknown fields per §5 / ASP-OUT-024 ruling.
    Returns the number of chunks upserted.
    """


@celery_app.task(name="app.ontology.manager.run_ontology_sync")
def run_ontology_sync(
    tenant_id: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> dict:
    """Celery entry point. Two modes:
      - Cron (no args): scheduled no-op in v1.0 pilot; logs
        ontology_sync_scheduled_trigger. Real scheduled sync
        logic is a future extension.
      - Explicit (tenant_id + db): introspects Postgres schema
        for the tenant and upserts chunks.
    Returns {"tenant_id": ..., "chunks_upserted": N, "skipped": N}.
    """
```

### §6.4 Error matrix (internal, not HTTP)

| Error condition | Exception | Downstream behaviour |
|---|---|---|
| Collection missing for tenant | `RAGCollectionMissingError` (new, S-6) | NLP handler converts to `HTTPException(503)`; Gateway renders RFC 7807 envelope with `type=/errors/rag-collection-missing` |
| ChromaDB corruption / IO error | `chromadb.errors.*` (library) | NLP handler wraps in 500 via existing generic error path; operator alerted via structlog |
| Empty retrieve result (collection exists, 0 matches) | **No exception** | NLP proceeds with empty `schema_context`; LLM response quality degrades silently. Fail-open, not fail-closed. Distinct from S-6 (missing collection). |
| `ChunkMetadata` validation failure at upsert | `ValidationError` (pydantic) | Ontology manager fails the task with `ontology_sync_failed` event; admin re-runs after fixing source data. Not caller-visible. |
| Embedding-model mismatch at collection open | Warning only (v1.0 per OQ-RAG-CACHE-01) | `rag_embedding_model_mismatch` structlog event; retrieval continues. ADR-035 (deferred) will govern fail-closed. |

### §6.5 Out-of-process boundaries

- Ontology manager runs in **celery-worker** process; RAG read runs in **ai-service** process.
- Shared ChromaDB storage via **`/chroma/data` volume** (PersistentClient).
- Cross-process write-visibility window: **5-minute TTL** on `_chroma_client` singleton per OQ-RAG-CACHE-01 Option B (`CHROMA_CLIENT_TTL_SECONDS=300`). A chunk upserted by ontology-sync at 02:00 UTC will become visible to ai-service's retrieve path within 5 minutes of its next call.
- No IPC, no Redis, no DB coupling between the two services beyond ChromaDB storage.

## §7 Request / Response Detail

Zone 1 internal contract — these are Python object shapes, not HTTP payloads. Shapes are nevertheless governed at Pydantic-model precision because they cross the ontology-manager / RAG boundary.

### §7.1 `ChunkResult` — retrieval output model

```python
# app/schemas/rag_schemas.py  (NEW FILE — also houses ChunkMetadata from §5)

from pydantic import BaseModel, ConfigDict
from typing import Literal


class ChunkResult(BaseModel):
    """One chunk returned by RAG retrieve()."""
    model_config = ConfigDict(extra="forbid")   # Zone 1 internal — forbid

    chunk_id: str                          # stable identifier (hash of tenant+table+chunk_type+content)
    document: str                          # the document text the LLM consumes
    metadata: ChunkMetadata                # full metadata per §5 contract
    distance: float                        # cosine distance [0.0, 2.0]; lower = more relevant
```

### §7.2 `format_chunks()` — LLM prompt injection format

Converts `list[ChunkResult]` to a structured string suitable for `{schema_context}` template substitution in the NLP prompt:

```
Table: {metadata.table_name}
{document}
---
Table: {metadata.table_name}
{document}
---
...
```

**Contract:**
- Empty list input → empty string output (`""`). NOT an error; fail-open semantics per §6.4.
- Order preserved from the retrieval result (ChromaDB returns in distance-ascending order; `format_chunks` preserves that order).
- Trailing `---` separator is included after every chunk (including the last) for consistent parser behaviour in future extensions.

### §7.3 `ChunkCandidate` — upsert input model

```python
class ChunkCandidate(BaseModel):
    """One chunk presented to upsert_chunks() by ASP-12 Ontology Manager.

    Distinct from ChunkResult (which is the read-path output shape).
    Candidate has no distance (pre-retrieval) and no chunk_id (computed
    by the upserter).
    """
    model_config = ConfigDict(extra="forbid")

    document: str
    metadata: ChunkMetadata
```

### §7.4 OQ-RAG-CACHE-01 resolution (reference)

**CLOSED** in ASP-FEAT-ASP-00 governance cycle. Recorded here for completeness:

- Policy: **5-minute TTL** on the `_chroma_client` singleton (`CHROMA_CLIENT_TTL_SECONDS=300`).
- Cross-container write visibility: ai-service reader sees celery-worker upserts within the TTL window.
- Re-initialisation emits `rag_chroma_client_initialised` with `reason=stale_ttl` for observability.
- Acceptable for pilot scale; Atrium-era will re-evaluate if concurrency grows.

### §7.5 Structlog event schema (RAG + Ontology Manager)

| Event | Emitter | Fields bound |
|---|---|---|
| `rag_chroma_client_initialised` | `get_chroma_client()` first call / TTL expiry | `path`, `client_type`, `reason` (`first_init` \| `stale_ttl`), `ttl_seconds` |
| `rag_embedding_function_initialised` | `_get_embedding_function()` first call | `model_name`, `ef_class` |
| `rag_embedding_model_mismatch` | `_check_embedding_model_snapshot()` on drift detection | `collection_name`, `stored_model`, `configured_model` |
| `rag_retrieve_start` | `retrieve()` entry | `tenant_id`, `top_k`, `has_exclude_tables`, `has_primary_entity` |
| `rag_chunks_returned` | `retrieve()` exit (success path) | `tenant_id`, `collection`, `count` |
| `rag_chunks_upserted` | `upsert_chunks()` success | `tenant_id`, `collection_name`, `count` |
| `rag_upsert_failed` | `upsert_chunks()` exception on `collection.upsert()` (post-validation, post-create) | `tenant_id`, `collection`, `error`, `count` |
| `rag_collection_not_found` | `retrieve()` catches `ChromaError` on missing collection | `tenant_id`, `collection`, `remediation` |
| `rag_collection_create_failed` | `upsert_chunks()` catches `ChromaError` on create | `tenant_id`, `error` |
| `rag_chunk_metadata_validation_failed` | `retrieve()` defensive ChunkMetadata parse on returned metadatas | `tenant_id`, `collection`, `errors` |
| `ontology_sync_scheduled_trigger` | `run_ontology_sync()` cron-path (no args) | (minimal — pilot no-op signal) |
| `ontology_sync_complete` | `run_ontology_sync()` with explicit args | `tenant_id`, `chunks_upserted`, `skipped` |

All events inherit `request_id`, `tenant_id`, `caller_module`, `caller_feature` from `structlog.contextvars` when present (ASP-FEAT-ASP-00 v1.0 contract).

## §8 Caller Integration Guide

RAG has **one caller**: `app.services.nlp._handle_nl_to_sql`. Ontology Manager is called by Celery beat and (future) an operator admin endpoint.

### §8.1 NLP integration contract

Sole caller: `_handle_nl_to_sql` in `app/services/nlp.py`. The call sequence is:

```python
from app.services.rag import get_chroma_client, retrieve, format_chunks
from app.services.rag import RAGCollectionMissingError

async def _handle_nl_to_sql(req, model, request_id):
    # ... payload validation ...

    try:
        chunks = await retrieve(
            query=payload.query,
            tenant_id=req.tenant_id,
            top_k=5,
            exclude_tables=schema_hints.exclude_tables if schema_hints else None,
        )
    except RAGCollectionMissingError:
        log.warning(
            "nl_to_sql_missing_ontology",
            tenant_id=req.tenant_id,
            request_id=request_id,
            remediation="run admin ontology_sync for this tenant",
        )
        raise HTTPException(
            status_code=503,
            detail={
                "detail": "Schema ontology not available for this tenant",
                "request_id": request_id,
                "remediation": "admin ontology_sync required",
            },
        )

    schema_context = format_chunks(chunks)
    # ... LLM call with schema_context injected into prompt ...
```

### §8.2 Error-path semantics (critical distinction)

Two failure modes, distinct treatment:

| Condition | Code path | HTTP outcome |
|---|---|---|
| **Tenant has no ontology seeded** (collection doesn't exist) | `retrieve()` raises `RAGCollectionMissingError` | NLP → `HTTPException(503)` → Gateway renders RFC 7807 envelope `type=/errors/rag-collection-missing` — **fail-closed** |
| **Tenant has ontology but retrieve returns 0 matches** (collection exists, query has no close chunks) | `retrieve()` returns `[]` normally | NLP proceeds with empty `schema_context`; LLM quality degrades silently — **fail-open** |
| **ChromaDB corruption / IO error** | library exception propagates | NLP 500 (Internal Server Error) via existing generic error path |

The fail-open path for empty-query-matches is intentional: a tenant with a sparse schema may still have legitimate natural-language queries that don't strongly match any table; the LLM should still attempt to answer (with lower confidence) rather than fail the whole call. Only the **missing-collection** case is fail-closed, because it represents a **setup/operational** defect (ontology sync hasn't run) rather than a query/data issue.

**Write-time boundary rule (ASP-OUT-027).** `ChunkMetadata` validation is enforced loudly at the **write-time boundary** (`upsert_chunks()` — raises `ValidationError` and aborts the batch) but is only **warned** at the read-time boundary (`retrieve()` — emits `rag_chunk_metadata_validation_failed` and proceeds). This asymmetry is deliberate: writes are the moment to reject malformed contract drift, while reads must preserve fail-open semantics for the live NLP path. A tenant that already has malformed data persisted (e.g. from a pre-governance upsert) can still be queried; the warning lets operators spot and remediate without breaking production.

### §8.3 Operator-side ontology sync (admin path)

Ontology sync for a new tenant is an operator-triggered event in v1.0 pilot:

```bash
# From ops host
docker compose exec celery-worker python -c "
from app.worker import celery_app
r = celery_app.send_task('app.ontology.manager.run_ontology_sync',
                          kwargs={'tenant_id': '<TENANT>'})
print(r.get(timeout=60))
"
```

A scheduled per-tenant sync via beat is out of scope for v1.0 (the current `ontology-sync-daily` beat fires a no-op). A future TSCD can wire up real per-tenant iteration when the tenant/schema registry is defined.

### §8.4 Consumer visibility of RAG failures

Consumers (PAP, LogiCRM) do NOT see RAG errors directly. Their visibility is:

- **503 on `nl_to_sql` with `remediation` field** → tenant ontology not seeded. Consumer action: contact ops to seed; retry later.
- **Low-quality `sql` result** → possibly no matching chunks but collection exists. Consumer action: treat as a generic low-confidence response; none of their business whether RAG failed silently.
- No other direct exposure of RAG state.

## §9 LLM and Prompt Design

**N/A — RAG makes no LLM calls.** All LLM invocation remains in the calling NLP handler and is governed by ASP-FEAT-ASP-01 v1.2. RAG is a vector retrieval + prompt-context-assembly service only; no prompt registry entries are owned by ASP-02 or ASP-12.

(Section retained per playbook 14-section template discipline, matching the Gateway spec's §9 treatment.)

## §10 Security Requirements

### §10.1 Tenant isolation — two layers

**Layer 1 (primary) — Collection-name scoping.**

Every tenant has a dedicated ChromaDB collection named `asp_schema_{tenant_id}`. `get_collection()` and `get_or_create_collection()` both use this scoped name. A query against tenant A's collection CAN NOT return chunks from tenant B because they live in separate collection-level namespaces inside ChromaDB.

**Layer 2 (defence-in-depth) — `tenant_id` filter in `where=` clause.** *(S-5 — net-new in v1.0, not yet implemented; spec first, implementation after Batch 3 acceptance.)*

Every `collection.query()` additionally filters on `metadata.tenant_id == tenant_id`:

```python
where = {"tenant_id": tenant_id}
if exclude_tables:
    where = {"$and": [
        {"tenant_id": tenant_id},
        {"table_name": {"$nin": exclude_tables}},
    ]}
```

**Rationale.** Any future bug in collection-name construction (typo, tenant_id mutation, shared pooled collection rewrite) cannot leak cross-tenant data because the metadata filter still applies. Two independent layers, either alone sufficient; both together is governed defence-in-depth. Performance cost is negligible on pilot-scale collections.

### §10.2 Embedding model — local inference only

**All embedding computation is local.** No external model API is called during embedding computation. `sentence-transformers` loads `all-MiniLM-L6-v2` from the local Hugging Face cache (pre-populated at Dockerfile build time — see I-RAG-02 `b4fbce9`). No query text, document content, or metadata leaves the container during embedding.

This is explicitly verified by the absence of any outbound HTTP client instantiation in `app/services/rag.py` or `app/ontology/manager.py`. The only external dependency is Anthropic (via the NLP service's LLM call), which receives the already-retrieved `schema_context` — NOT the raw chunks, NOT the query-embedding vectors.

### §10.3 `ChunkMetadata extra="forbid"` as a security property

The strict Pydantic model on chunk metadata is not just a type-safety feature — it's a **governed security property**. Specifically:

- Unknown metadata fields from a future ASP-12 version (e.g., a hypothetical `sensitive: true` flag added by a future extension) **cannot silently pass through** to the retrieval layer.
- If ASP-12 evolves to write a new metadata field, ASP-02's retrieve path must be updated in lockstep (via this spec or a future TSCD) so the contract is explicit.
- Drift between writer and reader is caught at write time (ValidationError on upsert) rather than silently propagating through to retrieval.

This is a narrow but real security property: it prevents "oh by the way we added a marker; make sure to filter on it" from being a runtime surprise.

### §10.4 ADR-004 compliance — `exclude_tables` enforcement

**Governed statement (verbatim, ASP-OUT-025 Note 3):**

> *`exclude_tables` enforcement at the ChromaDB metadata filter layer is the primary mechanism (ADR-004). The NLP prompt's `{exclude_tables}` placeholder is defence-in-depth only and must not be treated as the sole enforcement gate.*

**v1.0 preserves and reaffirms this**:

- The `where={"table_name": {"$nin": exclude_tables}}` clause in `retrieve()` is the primary enforcement. Chunks for excluded tables are never returned to the NLP handler.
- The `{exclude_tables}` prompt placeholder in the NLP system prompt is a secondary advisory — it reminds the LLM not to reference excluded tables even if some slipped through.
- If a future retrieval bug ever passed excluded-table chunks to the LLM, the prompt advisory is the last line of defence. Not acceptable to rely on it; documented as defence-in-depth only.

### §10.5 Data handling

- **No raw query text persisted.** `retrieve()` sends the query to ChromaDB for embedding; ChromaDB does not persist the query. No ASP-side storage.
- **No embedding vectors persisted.** Document embeddings are stored in ChromaDB tied to chunks. Query embeddings are transient — computed for the query, matched against document embeddings, discarded.
- **Structlog emits metadata, not content.** `rag_chunks_upserted` carries `tenant_id` and `count` — never raw document text. `rag_collection_not_found` carries `tenant_id` and `collection` name — never the user's query.

### §10.6 No new auth / rate-limit surface

RAG is not gateway-exposed, so inherits nothing from ASP-FEAT-ASP-00 v1.0's auth or rate limiter. Ontology sync is admin-triggered (Celery or ops shell), not caller-driven; access control is at the ops-host layer, not the application layer.

No new ADRs introduced by this section. ADR-001 (Zone 1 exclusion), ADR-004 (`exclude_tables` at RAG layer), and ADR-013 (tenant scoping on every DB query) all apply by reference.

---

**End of Batch 2 (§6–§10).** Batch 3 follows.

---

## §11 Implementation Checklist

Single-commit-per-item discipline. Commits already shipped are cited by short hash; items marked **NOT YET** are authored after Batch 3 acceptance.

| ID | Title | Owner stream | Status | Commit |
|---|---|---|---|---|
| **I-RAG-01** | `PersistentClient(path=CHROMA_PERSIST_PATH)` replacing ephemeral `Client()` | Stream B | **COMPLETE** | `a15e3fc` |
| **I-RAG-02** | Explicit `SentenceTransformerEmbeddingFunction(model_name=...)` binding + Dockerfile model preload + 5-minute TTL singleton | Stream B | **COMPLETE** | `b4fbce9` |
| **I-RAG-03** | Celery beat entry `ontology-sync-daily` (02:00 UTC; cron no-op in v1.0 pilot) | Stream B | **COMPLETE** | `40ff092` |
| **I-RAG-04** | Celery worker `-B` flag (beat scheduler enabled in `docker-compose.yml`) | Stream B | **COMPLETE** | `7538fb9` |
| **I-RAG-05** | `ChunkMetadata` Pydantic model in `app/schemas/rag_schemas.py` (§5 / S-4) — `extra="forbid"` | Stream B | **NOT YET** | — |
| **I-RAG-06** | `tenant_id` defence-in-depth in ChromaDB `where=` clause (§10.1 / S-5) — primary + secondary layer both present | Stream B | **NOT YET** | — |
| **I-RAG-07** | `RAGCollectionMissingError` exception class in `app/services/rag.py` + NLP `_handle_nl_to_sql` → 503 conversion (§6.4 / §8.2 / S-6) — fail-closed path | Stream B | **NOT YET** | — |
| **I-RAG-08** | AC verification suite — ≥25 ACs across S-1..S-7 + ADR-004 + cross-cutting (§12) | Stream B | **NOT YET** | — |
| **I-RAG-09** | Governance sync — `ASP-INDEX.md` ASP-02 GOVERNED row + `ASP-SCHEMA-CURRENT.md` (N/A marker for this feature) + `CLAUDE.md` state line; 4-way sha256 sync | Stream B | **NOT YET** | — |
| **I-RAG-10** | `.docx` render of this spec to `asp-projects/04-features/02-RAG/ASP-FEAT-ASP-02-v1_0.docx` via the `md2docx.js` tool | Stream B | **NOT YET** | — |

**Sequencing after Batch 3 acceptance:**

1. I-RAG-05 (Pydantic model; mechanical — unblocks I-RAG-06 typing)
2. I-RAG-06 (`where=` clause; cross-tenant probe covered by AC)
3. I-RAG-07 (exception class + NLP conversion; covered by AC)
4. I-RAG-08 (AC suite; 100 % pass mandatory before GOVERNED)
5. I-RAG-09 (governance sync; ADR-026.2 4-way verification)
6. I-RAG-10 (`.docx` render at final acceptance)

Each of I-RAG-05/06/07 is an independent commit per ASP-OUT-025 *"Each is an independent commit."*

---

## §12 Acceptance Criteria

**Target: 26 ACs across 8 blocks.** All must pass before GOVERNED closure (ASP-NOTE-011). Testing approach: `pytest tests/test_rag_v1.py` with Docker-compose fixtures for ai-service + celery-worker + postgres + chromadb volume.

### §12.1 Block S-1 — Persistence (4 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-S1-01** | ChromaDB collection survives `docker compose restart ai-service` | Seed tenant; restart; `get_collection('asp_schema_<tenant>')` returns same count |
| **AC-S1-02** | `chroma.sqlite3` present at `CHROMA_PERSIST_PATH` after first upsert | `ls /chroma/data/chroma.sqlite3` inside container exits 0 |
| **AC-S1-03** | `chroma_data` volume is mounted on BOTH `ai-service` AND `celery-worker` | `docker inspect` shows volume binding for both services |
| **AC-S1-04** | Collection written by celery-worker is readable by ai-service within TTL | Ontology sync upsert from worker; 1-second wait; retrieve() from ai-service returns chunks |

### §12.2 Block S-2 — Embedding function binding (4 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-S2-01** | Collection's effective EF is `SentenceTransformerEmbeddingFunction`, NOT the ChromaDB ONNX default | Log inspection: `rag_embedding_function_initialised` shows `ef_class="SentenceTransformerEmbeddingFunction"` |
| **AC-S2-02** | Collection metadata carries `asp_embedding_model` matching `settings.EMBEDDING_MODEL` | `collection.metadata["asp_embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"` |
| **AC-S2-03** | Ingest and retrieve both use the same EF (no asymmetric embedding) | Upsert + retrieve share the same `_get_embedding_function()` singleton; probe log shows single init event |
| **AC-S2-04** | First RAG request at cold start has zero outbound network latency (model pre-loaded at Dockerfile build) | Container `tcpdump` during first retrieve shows no HF Hub traffic |

### §12.3 Block S-3 — Embedding-model metadata snapshot (2 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-S3-01** | Collection metadata contains `asp_embedding_model` field after creation | `collection.metadata` includes the key |
| **AC-S3-02** | `_check_embedding_model_snapshot` logs a WARNING-level structlog event when the collection's `asp_embedding_model` metadata value does not match `settings.RAG_EMBEDDING_MODEL`. Collection is NOT invalidated — warn only (ADR-035 deferred). | Test: mutate `settings.RAG_EMBEDDING_MODEL` in a fixture; call retrieve; assert WARNING event captured and collection still usable. |

### §12.4 Block S-4 — `ChunkMetadata` Pydantic model (3 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-S4-01** | Valid chunk payload passes validation | `ChunkMetadata(tenant_id="t1", table_name="orders", chunk_type="table", source_version="v1")` succeeds |
| **AC-S4-02** | Unknown field raises `ValidationError` (`extra="forbid"`) | `ChunkMetadata(..., sensitive=True)` raises `ValidationError` with `extra_forbidden` error code |
| **AC-S4-03** | All four required fields must be present | Missing any of `tenant_id`, `table_name`, `chunk_type`, `source_version` raises `ValidationError` with `missing` error code |

### §12.5 Block S-5 — Tenant defence-in-depth (3 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-S5-01** | `where=` clause carries `tenant_id` when `exclude_tables` is set (`$and`-wrapped) | Inspect `collection.query()` kwargs; assert `where={"$and": [{"tenant_id": ...}, {"table_name": {"$nin": ...}}]}` |
| **AC-S5-02** | `where=` clause carries `tenant_id` even when `exclude_tables` is None | Inspect `collection.query()` kwargs; assert `where={"tenant_id": ...}` |
| **AC-S5-03** | Cross-tenant probe: tenant A upsert NOT visible to tenant B retrieve | Seed tenant A with distinctive chunk; call `retrieve(tenant_id="B", query=<match>)`; assert empty result |

### §12.6 Block S-6 — Fail-closed vs fail-open paths (3 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-S6-01** | Missing collection raises `RAGCollectionMissingError` | Call `retrieve(tenant_id="unseeded_t", ...)`; assert exact exception class (not `ChromaError`) |
| **AC-S6-02** | NLP `_handle_nl_to_sql` converts `RAGCollectionMissingError` to `HTTPException(503)` with RFC 7807 envelope | POST `nl_to_sql` for unseeded tenant; assert 503 + `type=/errors/rag-collection-missing` + `remediation` field |
| **AC-S6-03** | Empty retrieve result (collection exists, 0 matches) does NOT raise 503 — fail-open proceeds | Seed tenant; query with lexically unrelated text; assert 200 with degraded-quality `sql` response |

### §12.7 Block S-7 — Beat schedule (3 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-S7-01** | `ontology-sync-daily` present in `celery_app.conf.beat_schedule` | Assert key exists with `crontab(hour=2, minute=0)` |
| **AC-S7-02** | `monthly-cost-aggregation` present in `celery_app.conf.beat_schedule` (DEFECT-022 resolution) | Assert key exists with `crontab(hour=1, minute=0, day_of_month=1)` |
| **AC-S7-03** | `run_ontology_sync` task callable end-to-end via `celery_app.send_task(...)` | Send task with explicit tenant_id; assert SUCCESS + chunks persisted in ChromaDB |

### §12.8 Block ADR-004 compliance (2 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-ADR004-01** | `exclude_tables` populates a `$nin` filter in ChromaDB `where=` (not just the prompt) | Inspect `collection.query()` kwargs for `{"table_name": {"$nin": [...]}}` |
| **AC-ADR004-02** | Empty `exclude_tables` (None or `[]`) does NOT produce a filter error | `retrieve(query="x", tenant_id="t", exclude_tables=None)` returns normally; no `$nin` key in `where=` |

### §12.9 Block cross-cutting (2 ACs)

| # | Criterion | Verification |
|---|---|---|
| **AC-CC-01** | Retrieve path emits `rag_retrieve_start` and `rag_chunks_returned` structlog events | Log capture shows both events with `tenant_id`, `count` fields |
| **AC-CC-02** | Upsert path emits `rag_chunks_upserted` on success and `rag_upsert_failed` on exception | Force a ChromaDB IO error in a test; assert `rag_upsert_failed` captured |

**Pass threshold: 26 / 26. Anything less blocks GOVERNED closure.**

---

## §13 Open Questions

All Architect-deferred questions recorded for traceability. No open question blocks GOVERNED closure for v1.0.

| ID | Subject | Ruling | Owner |
|---|---|---|---|
| **OQ-1** | ADR-035 — Fail-closed on embedding-model mismatch (elevate from warning to hard failure) | **DEFERRED**. v1.0 default: warn-only via `rag_embedding_model_mismatch` structlog event. Re-evaluate if drift is observed in pilot. | Principal Architect |
| **OQ-2** | Migrate ChromaDB client away from in-proc to an HTTP-mode deployment (`HttpClient`) | **DEFERRED to Atrium**. v1.0 uses `PersistentClient` with shared volume per I-RAG-01. | Principal Architect |
| **OQ-3** | Per-tenant embedding model overrides (some tenants want a larger model) | **DEFERRED**. No tenant has requested; single `settings.EMBEDDING_MODEL` for all pilot tenants. Atrium-era reconsideration tied to tenant-level config surface. | Principal Architect |
| **OQ-RAG-CACHE-01** | `_chroma_client` singleton re-initialisation policy (long-lived vs TTL) | **CLOSED — Option B (5-minute TTL).** Shipped in I-RAG-02. See §7.4. | Principal Architect |

**No OPEN questions. All four deferrals are governance-acknowledged.**

---

## §14 Change Log

### v1.0-draft — 2026-04-18 / 2026-04-19

Joint ASP-02 + ASP-12 governance spec. Batch authoring per ASP-OUT-021 through ASP-OUT-025.

**Gap-matrix resolution (G-1 through G-10):**

| Gap | Disposition |
|---|---|
| G-1 PersistentClient | **RESOLVED** — I-RAG-01 `a15e3fc` |
| G-2 Explicit EF binding | **RESOLVED** — I-RAG-02 `b4fbce9` |
| G-3 `asp_embedding_model` metadata snapshot | **RESOLVED** — I-RAG-02 `b4fbce9` |
| G-4 Celery beat entry | **RESOLVED** — I-RAG-03 `40ff092` |
| G-5 Celery worker `-B` flag | **RESOLVED** — I-RAG-04 `7538fb9` |
| G-6 `ChunkMetadata` Pydantic governance | **SCOPED** — I-RAG-05 (S-4, pending) |
| G-7 Tenant defence-in-depth in `where=` | **SCOPED** — I-RAG-06 (S-5, pending) |
| G-8 Fail-closed missing-collection path | **SCOPED** — I-RAG-07 (S-6, pending) |
| G-9 Structlog event schema | **GOVERNED** — §7.5 table |
| G-10 Capabilities-exclusion permanence | **GOVERNED** — §6.1 verbatim language |

**Three net-new implementation items** (S-4 / S-5 / S-6) to ship in this spec cycle per ASP-OUT-025 sequencing.

**Stream B commits (chronological):**

- `a15e3fc` — I-RAG-01 PersistentClient
- `b4fbce9` — I-RAG-02 explicit EF + Dockerfile preload + 5-min TTL
- `40ff092` — I-RAG-03 Celery beat `ontology-sync-daily`
- `7538fb9` — I-RAG-04 Celery worker `-B` flag
- `d158221` — ASP-DEFECT-022 RESOLVED (cost aggregator asyncpg port; per-invocation engine pattern; governs §11 / §12.7 AC-S7-02)
- `afd0d2a` — Batch 2 authoring + ENGINEERING-PLAYBOOK loop-affinity lesson + COMMS-LOG housekeeping
- *(pending)* — Batch 3 authoring + Notes 1/3 verbatim alignment
- *(pending)* — I-RAG-05, I-RAG-06, I-RAG-07 (spec-only until accepted)
- *(pending)* — I-RAG-08 (AC suite)
- *(pending)* — I-RAG-09 (governance sync), I-RAG-10 (.docx render)

**DEFECT-022 resolution (2026-04-18 / 2026-04-19):**

Cost aggregator ported from psycopg2 (not in `requirements.txt`) to asyncpg via a per-invocation `create_async_engine()` + `engine.dispose()` pattern. Governed lesson (asyncpg event-loop affinity under Celery `asyncio.run()`) added to `ENGINEERING-PLAYBOOK.md` §12. AC-S7-02 locks `monthly-cost-aggregation` presence in beat schedule so the defect cannot silently regress.

**Governance trail:**

- ASP-OUT-021 — Batch 2 directive (superseded by ASP-OUT-022)
- ASP-OUT-022 — Batch 1 authoring + DEFECT-022 asyncpg port (CLOSED)
- ASP-OUT-024 — Batch 1 rulings + Batch 2 green light + loop-affinity lesson (OPEN → closes with this batch)
- ASP-OUT-025 — Batch 2 acceptance (with 3 verbatim-alignment notes, all applied) + Batch 3 green light (this batch) — **OPEN**

### Pre-v1.0 history (reference)

Earlier governance of RAG behaviour lived in two places:

- **ADR-001** (Zone 1 classification; RAG absent from `/capabilities`)
- **ADR-004** (`exclude_tables` at RAG layer as primary; prompt as defence-in-depth)

This v1.0 draft is the **first full governance spec** for ASP-02. Prior to this draft, RAG was documented only via ADRs + `ASP-INDEX.md` row + the `app/services/rag.py` source-level docstrings. That gap itself is why Stream B surfaced: four defects (I-RAG-01..04) were latent in production because no formal spec existed to enforce them.

### Anticipated v1.1

No v1.1 scope committed. Candidate items (all DEFERRED here):

- ADR-035 fail-closed embedding-model mismatch (OQ-1)
- HttpClient migration (OQ-2)
- Per-tenant embedding model overrides (OQ-3)
- Scheduled per-tenant ontology sync (currently operator-triggered per §8.3)

v1.1 will be authored when a trigger materialises (defect, capacity bottleneck, or tenant request).

---

**End of Batch 3 (§11–§14). End of ASP-FEAT-ASP-02 v1.0 draft.**

Awaiting Architect review of Batch 3 and green light for I-RAG-05 / I-RAG-06 / I-RAG-07 implementation sequence.
