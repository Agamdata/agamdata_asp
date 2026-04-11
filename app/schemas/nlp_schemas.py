"""
ASP-01 NLP Service — Pydantic Schemas (ADR-024)

Request payload and response result models for all NLP tasks.
All models use ConfigDict(extra='forbid') per ADR-008.

File: app/schemas/nlp_schemas.py
Spec: ASP-FEAT-ASP-01 v1.2, Sections 7.1 and 7.2
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Request Payload Models (Section 7.1)
# ---------------------------------------------------------------------------

class NlToSqlPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class IntentExtractPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class EntityRecognitionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class SentimentAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class ClassifyProbeResultPayload(BaseModel):
    """Payload for classify_probe_result task.

    [v1.1 AMENDED] F-1: post_submit_url and post_submit_status are OPTIONAL
    with default None. PAP may omit these fields entirely.
    """
    model_config = ConfigDict(extra="forbid")

    page_url: str
    page_type: Literal["FORM"]
    submitted_fields: dict[str, str]
    post_submit_url: str | None = None       # [v1.1] OPTIONAL — PAP may omit
    post_submit_status: int | None = None    # [v1.1] OPTIONAL — PAP may omit
    visible_text: str                         # Max 2000 chars (PAP caller-enforced)


# ---------------------------------------------------------------------------
# Response Result Models (Section 7.2)
# ---------------------------------------------------------------------------

class NlToSqlResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sql: str
    explanation: str
    tables_used: list[str]
    confidence: float
    clarification_needed: bool


class ExtractedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    value: str
    start: int
    end: int


class IntentExtractResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: str
    confidence: float
    entities: list[ExtractedEntity]
    secondary_intents: list[str]


class NamedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str   # PERSON, COMPANY, LOCATION, DATE, AMOUNT, PRODUCT, EMAIL, PHONE
    value: str
    start: int
    end: int


class EntityRecognitionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[NamedEntity]
    entity_count: int


class SentimentAspect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aspect: str
    sentiment: Literal["positive", "negative", "neutral"]
    score: float


class SentimentAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sentiment: Literal["positive", "negative", "neutral"]
    score: float
    aspects: list[SentimentAspect]


class ClassifyProbeResultOutput(BaseModel):
    """Response for classify_probe_result task.

    Outcome classification: success | validation_error | auth_redirect |
    server_error | unknown.
    """
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["success", "validation_error", "auth_redirect", "server_error", "unknown"]
    confidence: float
    error_messages: list[str]
    success_indicators: list[str]
    redirect_target: str | None
    reasoning: str
