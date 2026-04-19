"""
ASP-02 RAG Pydantic schemas.

ChunkMetadata is the governed contract for chunk metadata crossing the
ASP-12 Ontology Manager (writer) / ASP-02 RAG (reader) boundary.

Governed by ASP-FEAT-ASP-02 v1.0 §5 / §7. Authored per ASP-OUT-024 §5 and
ASP-OUT-026 I-RAG-05 rulings.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChunkMetadata(BaseModel):
    """Metadata for a single RAG chunk.

    Zone 1 internal — extra="forbid" intentional. Drift between ASP-12
    write contract and ASP-02 read contract must fail loudly. Unknown
    metadata fields (e.g. a hypothetical future `sensitive` flag) cannot
    silently pass through to retrieval; the writer MUST be updated in
    lockstep with the reader, or validation fails at upsert time.

    See ASP-FEAT-ASP-02 v1.0 §10.3 for the security rationale.
    """
    model_config = ConfigDict(extra="forbid")

    table_name: str
    module: str
    tenant_id: str
    chunk_type: Literal["schema", "example"]
