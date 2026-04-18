# ASP-FEAT-ASP-02 v1.0 — Implementation Log

Chronological record of rulings, findings, and phase-gate decisions made
during implementation of the RAG + Ontology Manager governance spec.
Entries are append-only. Consolidated into the AC-VERIFICATION report at
GOVERNED declaration.

Spec status at creation of this log: **spec draft not yet written.**
Implementation proceeding ahead of full spec authoring per Architect
directive 2026-04-18 19:30 IST (see first entry below for context).

---

## 2026-04-18 · Architect directive 19:30 IST + 19:45 correction

**Original 19:30 directive (not delivered to this session — see routing
note below).** Lifted the pilot-environment hold; green-lit Stream A
(migration 024 spec draft) and Stream B (RAG fixes: I-RAG-01/02/03).
Substance re-sent as the 19:55 RESUME message.

**19:45 correction (received).** *"PAP testing is paused"* in the 19:30
directive was inaccurate. Correct position: **PAP testing is complete
for the current phase. PAP verifies new features as they land. ADR-034
CI handles schema change detection automatically.** No operational
change — Stream A and Stream B priorities are unchanged.

**Routing note.** The 19:30 directive was not delivered to this
(ASP Dev Team) session. A concurrent mis-route (`DEV-OUT-010` for PAP
Dev Team arriving here at 18:45 IST) suggests the Architect is running
parallel sessions. Mis-route raised; Option A confirmed at 19:55 IST
(DEV-OUT-010 belongs to PAP session; no ASP action on its four items).
RESUME instruction arrived explicit in the 19:55 message.

**Status.** INFORMATIONAL — recorded to preserve the audit trail.

---

## 2026-04-18 · I-RAG-01 — PersistentClient fix

**Scope.** Replace `chromadb.Client()` (ephemeral, in-process) with
`chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)`; wire the
persistence path into `docker-compose.yml` as a named volume shared
between `ai-service` and `celery-worker`; verify round-trip
persistence across container restarts and cross-container visibility.

**Code changes.**

- `app/config.py` — added `CHROMA_PERSIST_PATH: str = "/chroma/data"`
  with rationale comment.
- `app/services/rag.py` — `get_chroma_client()` now returns
  `chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)`.
  Module docstring corrected: the embedding function is
  `ONNXMiniLM_L6_V2` (ChromaDB default), **not** the
  `sentence-transformers/all-MiniLM-L6-v2` the old docstring claimed.
  First-init emits `rag_chroma_client_initialised` with the path and
  client-type bound for observability.
- `docker-compose.yml`:
  - Added `CHROMA_PERSIST_PATH: /chroma/data` env on both `ai-service`
    and `celery-worker` (matches the config default for clarity).
  - New named volume `chroma_data:/chroma/data` mounted on both.
  - Added `./app:/app/app` code mount on `celery-worker` — previously
    absent, meaning celery-worker ran from the baked image while
    ai-service ran from the mount. See "Side-effect finding" below.
  - Declared `chroma_data` in the top-level `volumes:` block.

**Verification (smoke tests against live pilot environment).**

| Test | Result |
|---|---|
| `PersistentClient` initialises at `/chroma/data`; SQLite file created | ✅ `chroma.sqlite3` present, 167 KB |
| Probe collection created with custom metadata `{hnsw:space, probe_marker}` | ✅ Metadata readable back via `client.get_collection(name).metadata` |
| Collection survives `docker compose restart ai-service` | ✅ `collection count after restart: 1`, metadata intact |
| Volume is a shared mount across containers (inode parity) | ✅ Both containers see `98469 /chroma/data/chroma.sqlite3 167936` — same inode |
| celery-worker can read collections written by ai-service (after code-mount fix) | ✅ `celery-worker (post-mount-fix) collection count: 1` |
| celery-worker can write (`upsert_chunks`) and ai-service reads the write | ✅ `ai-service (post-reload) collection count: 2` — probe + smoke tenant |
| ONNX model downloaded on first embedding computation (79 MB) | ✅ `rag_chunks_upserted count=1 tenant_id=smoke_ontology_*`; took ~1:51 |
| Teardown — test collections deleted; `remaining collection count: 0` | ✅ Live state clean |

**Milestone.** This is the **first time in this pilot environment's history
that an embedding has been computed and a ChromaDB collection has been
populated.** The earlier probe (pre-I-RAG-01) confirmed the ONNX model cache
had never been populated. G-1 is now closed — persistence works, cross-container
visibility works, the embedding pipeline executes end-to-end.

**Side-effect finding — existing celery-worker code-drift.**

While diagnosing the initial cross-container failure (celery-worker saw
zero collections despite the shared volume), the root cause was that
celery-worker had no `./app:/app/app` bind mount in `docker-compose.yml`
— it ran from the baked image while ai-service ran from the mount.
This is a **pre-existing gap not introduced by this work**, but it means
any code change not committed into a rebuilt image would silently
diverge between ai-service and celery-worker during development. Fixed
as part of I-RAG-01. Recommend back-porting this parity in any future
compose review.

**Finding deferred to later item — ai-service client cache invalidation.**

Within a single running ai-service process, the `_chroma_client` module
singleton caches the collection registry. If the Ontology Manager
writes a new collection via celery-worker, a running ai-service will
**not** see that new collection until the process restarts or the
singleton is invalidated. The smoke test confirmed this by needing
`importlib.reload(rag)` before ai-service could see the celery-worker
write. Spec §13 Open Questions will surface:

- **OQ-RAG-CACHE-01** — Collection registry cache invalidation policy
  in ai-service. Options: (a) per-request refresh (expensive),
  (b) TTL + polling (brittle), (c) admin-trigger on Ontology Manager
  sync completion (operator-aware), (d) accept restart-after-sync as
  operator SOP (simplest; rare event). Defer until Architect rules.

**Finding deferred — ONNX cache is NOT persisted in the named volume.**

The 79 MB ONNX model downloaded to `/root/.cache/chroma/` inside the
container filesystem, NOT into the `chroma_data` named volume. Container
rebuilds will discard the model and re-trigger the ~2-minute download
on first call. This is I-RAG-WARMUP territory (warmup policy a/b/c
from the pre-spec survey). Leaving unchanged in I-RAG-01; I-RAG-02
will address by either (a) startup warmup, (b) image preload, or
(c) switching to `sentence-transformers` and pre-downloading at build.

**Status.** I-RAG-01 COMPLETE. Live state clean (0 collections). No
real tenant data affected. Ready to commit.

---

## 2026-04-18 · Ahead-of-spec note on I-RAG-02 and I-RAG-03

I-RAG-01 was executed before the ASP-FEAT-ASP-02 spec itself has been
authored. The numbered labels `I-RAG-01/02/03` from the Architect's
19:55 RESUME message are therefore ad-hoc for now; they will be
formalised in §11 Implementation Checklist when the spec is drafted.

I-RAG-01 (persistence) is standalone and can ship without the spec.
I-RAG-02 (explicit embedding) will depend on the ADR-035 ruling
(proposed during pre-spec survey) that locks `RAG_EMBEDDING_MODEL`
config and snapshots it into collection metadata. I-RAG-03 (Celery
beat schedule for ontology sync) will need to respect the
OQ-RAG-CACHE-01 decision above — if the operator-aware or
restart-after-sync policy is chosen, periodic automated sync via
beat becomes less attractive.

These two dependencies will be surfaced explicitly in the Batch 1
draft of the spec when Stream A completes.
