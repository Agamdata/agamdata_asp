"""
ASP-01 NLP Service — Pydantic Schemas (ADR-024)

Request payload and response result models for all NLP tasks.
All models use ConfigDict(extra='forbid') per ADR-008.

File: app/schemas/nlp_schemas.py
Spec: ASP-FEAT-ASP-01 v1.2, Sections 7.1 and 7.2
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


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


# ---------------------------------------------------------------------------
# suggest_screen_mapping — BP-10 / PAP-ASP-REQ-ASP-01 v2.0 (ASP-OUT-020)
# ---------------------------------------------------------------------------

class AvailableModule(BaseModel):
    """One module entry from the caller's available-modules list.

    Used as input to the suggest_screen_mapping LLM to constrain its
    output. The LLM must only return module_key values present in this
    list — handler validates post-parse (AC-BP10-03 hallucination guard).
    """
    model_config = ConfigDict(extra="forbid")
    module_key: str
    module_name: str


class SuggestScreenMappingPayload(BaseModel):
    """Validated payload for suggest_screen_mapping task.

    NLP service convention: payloads use extra="ignore" per ADR-033?
    No — ADR-033 scopes extra="ignore" to the generation service only.
    NLP retains extra="forbid" per ADR-008. ASP-OUT-020 directive says
    extra="ignore" — Dev Team honours the directive; flagged as a minor
    convention drift from NLP precedent, no impact on behaviour because
    this is a new task with no prior contract.
    """
    model_config = ConfigDict(extra="ignore")   # per ASP-OUT-020 directive
    page_url: str
    page_title: Optional[str] = None
    page_type: Optional[str] = None
    available_modules: list[AvailableModule]

    @field_validator("available_modules")
    @classmethod
    def _reject_empty_available_modules(cls, v):
        """AC-BP10-05: empty list → 422. No modules to choose from means
        no meaningful suggestion is possible; caller contract requires at
        least one option."""
        if len(v) == 0:
            raise ValueError(
                "available_modules must be a non-empty list — at least "
                "one module is required for the LLM to produce a meaningful "
                "suggestion. To indicate 'no modules available', do not "
                "invoke suggest_screen_mapping; handle that state caller-side."
            )
        return v


class SuggestScreenMappingResult(BaseModel):
    """Output for suggest_screen_mapping.

    All fields optional with safe defaults. Handler post-parse enforces
    that suggested_module_key (when non-null) matches one of
    payload.available_modules; hallucinated keys are scrubbed to null
    (AC-BP10-03).
    """
    model_config = ConfigDict(extra="ignore")
    suggested_module_key: Optional[str] = None
    suggested_screen_name: Optional[str] = None
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# extract_test_entities — F-03-02 / PAP-ASP-REQ-ASP-02 v1.0 (ASP-OUT-036)
# ---------------------------------------------------------------------------
#
# Service-naming note (ASP-OUT-034 flag acknowledged by ASP-OUT-036): the
# Architect directive refers to this task as "ASP-02 (nlp)" but in the repo
# ASP-02 is the RAG service (governed under ASP-FEAT-ASP-02 v1.0) and NLP is
# ASP-01. The task lives on the NLP service — `service_type="nlp"` in the
# prompt_templates row (migration 027) and is dispatched through
# app/services/nlp.py. Directive body unambiguously targets NLP; the ASP-02
# label in the directive header is an informal grouping.

class TestEntityContext(BaseModel):
    """Context accompanying a freeform text for entity extraction.

    Caller supplies the screen/module/category triple so the LLM can scope
    its extraction to the relevant test surface. None of the three are
    validated against an allowlist at this layer — that is caller-side.
    """
    model_config = ConfigDict(extra="ignore")  # F-03-02 / ASP-OUT-036
    screen_key: str
    module_key: str
    category: str


class ExtractTestEntitiesPayload(BaseModel):
    """Payload for the extract_test_entities task."""
    model_config = ConfigDict(extra="ignore")
    text: str
    context: TestEntityContext


class TestEntities(BaseModel):
    """The four governed entity buckets. All list[str] with [] defaults so
    the LLM may return any subset without tripping 422 on the missing keys.

    AC-F3-12 (empty lists valid) and AC-F3-13 (low-confidence all-empty)
    are both satisfied by this shape.
    """
    model_config = ConfigDict(extra="ignore")
    required_fields: list[str] = []
    actions: list[str] = []
    validation_cases: list[str] = []
    success_outcomes: list[str] = []


class ExtractTestEntitiesResult(BaseModel):
    """Output of extract_test_entities."""
    model_config = ConfigDict(extra="ignore")
    entities: TestEntities
    confidence: float = 0.0
