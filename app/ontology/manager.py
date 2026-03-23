"""
ASP-12 Ontology Manager

Manages schema/ontology metadata synced into ChromaDB for RAG retrieval.
Runs as a Celery beat periodic task in cron mode.
"""
import hashlib
import json
import structlog
from typing import Optional

from app.services.rag import upsert_chunks

log = structlog.get_logger()


def _chunk_id(tenant_id: str, table_name: str, chunk_type: str) -> str:
    key = f"{tenant_id}:{table_name}:{chunk_type}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def build_schema_chunk(
    tenant_id: str,
    table_name: str,
    module: str,
    columns: list[dict],
    description: str = "",
) -> dict:
    """
    Build a ChromaDB chunk from a table schema definition.
    columns: list of { "name": str, "type": str, "description": str (optional) }
    """
    col_text = "\n".join(
        f"  {c['name']} ({c['type']}){': ' + c.get('description','') if c.get('description') else ''}"
        for c in columns
    )
    text = f"Table: {table_name}\n{description}\nColumns:\n{col_text}"

    return {
        "id": _chunk_id(tenant_id, table_name, "schema"),
        "text": text,
        "metadata": {
            "table_name": table_name,
            "module": module,
            "tenant_id": tenant_id,
            "chunk_type": "schema",
        },
    }


def sync_schema(
    tenant_id: str,
    module: str,
    schema_definitions: list[dict],
) -> None:
    """
    Upsert schema definitions for a tenant into ChromaDB.
    schema_definitions: list of { "table_name": str, "description": str, "columns": list, "module": str }
    """
    chunks = []
    for defn in schema_definitions:
        chunk = build_schema_chunk(
            tenant_id=tenant_id,
            table_name=defn["table_name"],
            module=defn.get("module", module),
            columns=defn.get("columns", []),
            description=defn.get("description", ""),
        )
        chunks.append(chunk)

        # Also add example queries if provided
        for i, example in enumerate(defn.get("examples", [])):
            chunks.append({
                "id": _chunk_id(tenant_id, f"{defn['table_name']}_example_{i}", "example"),
                "text": f"Example for {defn['table_name']}: {example}",
                "metadata": {
                    "table_name": defn["table_name"],
                    "module": defn.get("module", module),
                    "tenant_id": tenant_id,
                    "chunk_type": "example",
                },
            })

    if chunks:
        upsert_chunks(tenant_id, chunks)
        log.info("ontology_sync_complete", tenant_id=tenant_id, module=module, chunks=len(chunks))


# --- Celery task (cron mode) ---
# Registered in worker.py; runs periodically to keep ChromaDB in sync.
def run_ontology_sync(tenant_id: str, module: str, schema_definitions: list[dict]) -> None:
    """Entry point for Celery periodic task."""
    try:
        sync_schema(tenant_id, module, schema_definitions)
    except Exception as e:
        log.error("ontology_sync_failed", tenant_id=tenant_id, module=module, error=str(e))
        raise
