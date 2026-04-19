"""
ASP-02 RAG Service

Persistence: chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)
Collection name: asp_schema_{tenant_id}
Embedding model: settings.RAG_EMBEDDING_MODEL, bound explicitly via
SentenceTransformerEmbeddingFunction at BOTH ingest (upsert_chunks) AND
query (retrieve) call sites. Default: sentence-transformers/all-MiniLM-L6-v2,
pre-downloaded into the container image at Dockerfile build time so first
call has zero network latency. Closes G-3 from the pre-spec survey.

Each chunk stored in ChromaDB MUST have metadata:
{ "table_name": str, "module": str, "tenant_id": str, "chunk_type": "schema"|"example" }

Each collection stores its owning embedding model in metadata:
{ "hnsw:space": "cosine", "asp_embedding_model": <model name> }
so drift at open time can be detected (warn today; ADR-035 will lock the
fail-closed policy when the spec is accepted).

Implementation history:
- I-RAG-01 (2026-04-18): ephemeral -> PersistentClient.
- I-RAG-02 (2026-04-18): explicit embedding + metadata snapshot +
  5-minute TTL on the _chroma_client singleton (OQ-RAG-CACHE-01 Option B).
"""
import time
from typing import Optional

import chromadb
import structlog
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pydantic import ValidationError

from app.config import settings
from app.schemas.rag_schemas import ChunkMetadata

log = structlog.get_logger()

_chroma_client: Optional["chromadb.api.ClientAPI"] = None
_chroma_client_init_at: float = 0.0
_embedding_fn: Optional[SentenceTransformerEmbeddingFunction] = None


def _get_embedding_function() -> SentenceTransformerEmbeddingFunction:
    """Process-wide singleton embedding function.

    Lazily constructed on first access. Model is identified by
    settings.RAG_EMBEDDING_MODEL and pre-downloaded at image build time
    (Dockerfile), so construction never performs a network fetch in the
    steady state.
    """
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=settings.RAG_EMBEDDING_MODEL,
        )
        log.info(
            "rag_embedding_function_initialised",
            model_name=settings.RAG_EMBEDDING_MODEL,
            ef_class=type(_embedding_fn).__name__,
        )
    return _embedding_fn


def get_chroma_client() -> "chromadb.api.ClientAPI":
    """Return the process-wide ChromaDB PersistentClient.

    Initialised lazily on first access. Re-initialised after
    settings.CHROMA_CLIENT_TTL_SECONDS (pilot default 300s / 5 min) so
    cross-process writes from celery-worker's Ontology Manager become
    visible in ai-service without requiring a restart. Closes OQ-RAG-CACHE-01.
    """
    global _chroma_client, _chroma_client_init_at
    now = time.monotonic()
    stale = (
        _chroma_client is not None
        and (now - _chroma_client_init_at) > settings.CHROMA_CLIENT_TTL_SECONDS
    )
    if _chroma_client is None or stale:
        reason = "stale_ttl" if stale else "first_init"
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_PATH)
        _chroma_client_init_at = now
        log.info(
            "rag_chroma_client_initialised",
            path=settings.CHROMA_PERSIST_PATH,
            client_type=type(_chroma_client).__name__,
            reason=reason,
            ttl_seconds=settings.CHROMA_CLIENT_TTL_SECONDS,
        )
    return _chroma_client


def _collection_name(tenant_id: str) -> str:
    return f"asp_schema_{tenant_id}"


def _check_embedding_model_snapshot(collection) -> None:
    """Warn if an existing collection's snapshotted embedding model does not
    match settings.RAG_EMBEDDING_MODEL.

    Fail-closed policy (ADR-035 proposed) is deferred until the spec is
    accepted; for now we log a warning so operators can spot drift.
    """
    stored = (collection.metadata or {}).get("asp_embedding_model")
    if stored and stored != settings.RAG_EMBEDDING_MODEL:
        log.warning(
            "rag_embedding_model_mismatch",
            collection=collection.name,
            stored_model=stored,
            configured_model=settings.RAG_EMBEDDING_MODEL,
            remediation="reindex required — stored and configured embedding "
                        "models produce different vectors",
        )


async def retrieve(
    query: str,
    tenant_id: str,
    primary_entity: Optional[str],
    exclude_tables: list[str],
    top_k: int = 8,
) -> list[str]:
    """
    Retrieve relevant schema chunks for a query.
    exclude_tables is enforced via ChromaDB metadata filter BEFORE passing to LLM
    (ADR-004). The embedding function is bound explicitly at get_collection time
    so the query embedding is computed with the same model used at ingest.
    """
    client = get_chroma_client()
    collection_name = _collection_name(tenant_id)

    try:
        collection = client.get_collection(
            collection_name,
            embedding_function=_get_embedding_function(),
        )
    except Exception:
        log.warning("rag_collection_not_found", tenant_id=tenant_id, collection=collection_name)
        return []

    _check_embedding_model_snapshot(collection)

    # exclude_tables filter — ADR-004 enforcement at the metadata layer
    where = None
    if exclude_tables:
        where = {"table_name": {"$nin": exclude_tables}}

    biased_query = f"{primary_entity} related: {query}" if primary_entity else query

    results = collection.query(
        query_texts=[biased_query],
        n_results=min(top_k, collection.count()),
        where=where,
    )

    # I-RAG-05 (ASP-OUT-026): parse returned metadatas through ChunkMetadata
    # to surface any read/write contract drift as a structured warning. The
    # caller contract (list[str] of documents) is preserved; validation is
    # defensive instrumentation only — we do NOT drop chunks on validation
    # failure at read time, only warn.
    metadatas_lists = results.get("metadatas") or []
    for meta in (metadatas_lists[0] if metadatas_lists else []):
        try:
            ChunkMetadata(**(meta or {}))
        except ValidationError as ve:
            log.warning(
                "rag_chunk_metadata_validation_failed",
                tenant_id=tenant_id,
                collection=collection_name,
                errors=ve.errors(include_url=False),
            )

    return results["documents"][0] if results["documents"] else []


def format_chunks(chunks: list[str]) -> str:
    return "\n\n".join(chunks)


def upsert_chunks(
    tenant_id: str,
    chunks: list[dict],
) -> None:
    """
    Upsert schema chunks into ChromaDB.
    Each chunk: { "id": str, "text": str, "metadata": dict }
    Metadata MUST include: table_name, module, tenant_id, chunk_type.
    Collection-level metadata snapshots the embedding model for drift
    detection.
    """
    client = get_chroma_client()
    collection_name = _collection_name(tenant_id)

    try:
        collection = client.get_or_create_collection(
            collection_name,
            metadata={
                "hnsw:space": "cosine",
                "asp_embedding_model": settings.RAG_EMBEDDING_MODEL,
            },
            embedding_function=_get_embedding_function(),
        )
    except Exception as e:
        log.error("rag_collection_create_failed", error=str(e))
        raise

    _check_embedding_model_snapshot(collection)

    # I-RAG-05 (ASP-OUT-026): validate every chunk's metadata against the
    # governed ChunkMetadata contract BEFORE upsert. extra="forbid" ensures
    # any drift from the ASP-12 write contract raises ValidationError and
    # the whole batch fails loudly rather than persisting malformed data.
    validated: list[dict] = []
    for c in chunks:
        meta = ChunkMetadata(**c["metadata"])           # raises ValidationError
        validated.append(meta.model_dump())

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = validated

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    log.info("rag_chunks_upserted", tenant_id=tenant_id, count=len(chunks),
             collection=collection_name)
