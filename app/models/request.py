from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, Any, List


class UserContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    role: str
    maturity_level: Literal["L0", "L1", "L2", "L3"] = "L2"
    permissions: list[str] = []


class UIContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_screen: Optional[str] = None
    active_filters: Optional[dict[str, Any]] = None
    active_record_id: Optional[str] = None


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    turn: int
    generated_sql: Optional[str] = None  # include if assistant turn produced SQL


class SchemaHints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_entity: Optional[str] = None
    related_entities: list[str] = []
    exclude_tables: list[str] = []


class InvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_type: Literal[
        "nlp", "generation", "doc_intelligence", "prediction", "dashboard_intelligence"
    ]
    task: str                           # validated per service in service layer
    caller_module: str
    caller_feature: Optional[str] = Field(default=None, max_length=128)
    # ^ ASP-FEAT-ASP-00 v1.0 §7 / AC-S6-01..05. Opaque to ASP routing; logged
    #   to structlog and persisted verbatim to cost_events.caller_feature.
    #   Not validated against any registry; NULL = pre-feature or non-PAP caller.
    tenant_id: str
    quality_tier: Literal["standard", "enhanced", "premium"] = "standard"
    session_id: Optional[str] = None
    user_context: Optional[UserContext] = None
    ui_context: Optional[UIContext] = None
    conversation_history: list[ConversationTurn] = []
    schema_hints: Optional[SchemaHints] = None
    payload: dict[str, Any]             # service-specific, validated in service layer


class WebhookRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caller_module: str
    callback_url: str
    secret: Optional[str] = None
