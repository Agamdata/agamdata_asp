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


# --- Celery task (cron mode) -----------------------------------------------
# I-RAG-03 (ASP-OUT-009, 2026-04-18): registered as a Celery task so the
# beat schedule in app/worker.py can trigger it. All args are optional so
# the daily cron invocation (no args) is valid; manual invocations with
# explicit (tenant_id, module, schema_definitions) retain the existing
# one-shot behaviour.
#
# Cron-path (no args) is currently a structured no-op: it logs that the
# scheduled trigger fired. A follow-up spec task will extend the cron path
# to iterate active tenants + resolve their schema registry. The present
# pilot does not have a tenant/schema registry; shipping the cron entry
# with an observable no-op satisfies ASP-OUT-009 without accidentally
# seeding speculative data.

from typing import Optional

from app.worker import celery_app


@celery_app.task(name="app.ontology.manager.run_ontology_sync")
def run_ontology_sync(
    tenant_id: Optional[str] = None,
    module: Optional[str] = None,
    schema_definitions: Optional[list[dict]] = None,
) -> None:
    """Celery task — unified entry point for manual and scheduled sync."""
    if tenant_id is None and module is None and not schema_definitions:
        # Scheduled (cron) path — Celery beat invokes with no args.
        log.info(
            "ontology_sync_scheduled_trigger",
            note="pilot no-op — tenant/schema registry not yet defined; "
                 "follow-up spec task extends this path to iterate active tenants",
        )
        return

    # Manual path — caller supplied tenant + module + schemas.
    if tenant_id is None or module is None or schema_definitions is None:
        log.error(
            "ontology_sync_failed",
            reason="partial_args",
            tenant_id=tenant_id,
            module=module,
            schemas_provided=schema_definitions is not None,
        )
        raise ValueError(
            "run_ontology_sync requires all three of (tenant_id, module, "
            "schema_definitions) when invoked manually; partial args rejected"
        )
    try:
        sync_schema(tenant_id, module, schema_definitions)
    except Exception as e:
        log.error("ontology_sync_failed", tenant_id=tenant_id, module=module, error=str(e))
        raise
