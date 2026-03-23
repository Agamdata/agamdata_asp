"""
ASP-02 RAG Service

Uses ChromaDB locally, OpenSearch/pgvector in production.
Collection name: asp_schema_{tenant_id}
Embedding model: sentence-transformers/all-MiniLM-L6-v2

Each chunk stored in ChromaDB MUST have metadata:
{ "table_name": str, "module": str, "tenant_id": str, "chunk_type": "schema"|"example" }
"""
from typing import Optional
import chromadb
import structlog

log = structlog.get_logger()

_chroma_client: Optional[chromadb.Client] = None


def get_chroma_client() -> chromadb.Client:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.Client()
    return _chroma_client


def _collection_name(tenant_id: str) -> str:
    return f"asp_schema_{tenant_id}"


async def retrieve(
    query: str,
    tenant_id: str,
    primary_entity: Optional[str],
    exclude_tables: list[str],
    top_k: int = 8,
) -> list[str]:
    """
    Retrieve relevant schema chunks for a query.
    exclude_tables is enforced via ChromaDB metadata filter BEFORE passing to LLM.
    """
    client = get_chroma_client()
    collection_name = _collection_name(tenant_id)

    try:
        collection = client.get_collection(collection_name)
    except Exception:
        log.warning("rag_collection_not_found", tenant_id=tenant_id, collection=collection_name)
        return []

    # Build where filter — exclude tables if specified (security: enforced in metadata, not just prompt)
    where = None
    if exclude_tables:
        where = {"table_name": {"$nin": exclude_tables}}

    # Bias query toward primary_entity if provided
    biased_query = f"{primary_entity} related: {query}" if primary_entity else query

    results = collection.query(
        query_texts=[biased_query],
        n_results=min(top_k, collection.count()),
        where=where,
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
    Metadata MUST include: table_name, module, tenant_id, chunk_type
    """
    client = get_chroma_client()
    collection_name = _collection_name(tenant_id)

    try:
        collection = client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        log.error("rag_collection_create_failed", error=str(e))
        raise

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    log.info("rag_chunks_upserted", tenant_id=tenant_id, count=len(chunks))
