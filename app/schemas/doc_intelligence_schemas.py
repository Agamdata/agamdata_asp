"""
ASP-04 Doc Intelligence — Pydantic schemas.

Governed by ASP-FEAT-ASP-04 v1.0 §5.2 / §7.2.

Two existing output models (ExtractDocumentOutput, ClassifyDocumentOutput)
are migrated from their inline definitions in
`app/services/doc_intelligence.py` to this dedicated module per
§5.2 / I-DOC-04. The service module imports them back — zero
behavioural change for the existing two tasks.

Two new models (LineItem, ExtractInvoiceOutput) ship with I-DOC-07
(extract_invoice handler) but are defined here for co-location.

One new response model (DocumentUploadResponse) ships with I-DOC-05
(upload endpoint).

All payload / LLM-output models use `ConfigDict(extra="ignore")` per
ADR-033. The response contract (`DocumentUploadResponse`) is the
strict side — `extra="forbid"` per ADR-008.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Existing output models — migrated in from app/services/doc_intelligence.py
# ---------------------------------------------------------------------------

class ExtractDocumentOutput(BaseModel):
    """Generic document extraction output. Governed unchanged from the
    pre-governance state for consumer contract lock (ASP-FEAT-ASP-04
    v1.0 §5.2)."""
    model_config = ConfigDict(extra="ignore")
    fields:      dict
    tables:      list[dict]
    confidence:  float
    page_count:  int


class ClassifyDocumentOutput(BaseModel):
    """Document classification output. Governed unchanged."""
    model_config = ConfigDict(extra="ignore")
    doc_type:          str
    confidence:        float
    suggested_fields:  list[str]


# ---------------------------------------------------------------------------
# NEW — F-DOC-01 (extract_invoice)  — ASP-FEAT-ASP-04 v1.0 §5.2 / §9.3
# ---------------------------------------------------------------------------

class LineItem(BaseModel):
    """One line item on an invoice.

    Quantitative fields all optional — real invoices often omit
    unit_price or quantity (e.g. service-based invoices with
    amount-only entries).
    """
    model_config = ConfigDict(extra="ignore")
    description:  str
    quantity:     Optional[float] = None
    unit_price:   Optional[float] = None
    amount:       Optional[float] = None


class ExtractInvoiceOutput(BaseModel):
    """Invoice-specific extraction output.

    Directive-verbatim shape per ASP-OUT-042 Q-6. All fields nullable —
    real invoices are inconsistent; the LLM extracts what is present
    and missing fields return null (never errors).

    `invoice_date` / `due_date` are deliberately `Optional[str]` and
    not `Optional[date]` (§5.2 rationale): real invoices contain
    dates in dozens of formats. Downstream consumers normalise.
    """
    model_config = ConfigDict(extra="ignore")
    vendor:          Optional[str]       = None
    invoice_number:  Optional[str]       = None
    invoice_date:    Optional[str]       = None
    due_date:        Optional[str]       = None
    line_items:      list[LineItem]      = []
    subtotal:        Optional[float]     = None
    tax_amount:      Optional[float]     = None
    total_amount:    Optional[float]     = None
    currency:        Optional[str]       = None
    payment_terms:   Optional[str]       = None


# ---------------------------------------------------------------------------
# NEW — upload endpoint response (§5.3 / §7.2)  — I-DOC-05
# ---------------------------------------------------------------------------

class DocumentUploadResponse(BaseModel):
    """Response body for POST /api/v1/ai/documents.

    Strict response contract (`extra="forbid"`) per ADR-008 — any
    drift from this shape is a regression. Field values:

    - document_id: UUID as string (server-generated; not client-suppliable)
    - storage_path: MinIO object key, tenant-prefixed per ADR-013
    - tenant_id: echoed from verify_api_key (NOT read from request body)
    - original_filename: sanitised (path separators stripped, 255-char cap)
    - uploaded_at: ISO-8601 UTC
    """
    model_config = ConfigDict(extra="forbid")
    document_id:       str
    storage_path:      str
    tenant_id:         str
    original_filename: str
    uploaded_at:       str
