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
    tenant_id: str
    quality_tier: Literal["standard", "enhanced", "premium"] = "standard"
    session_id: Optional[str] = None
    user_context: Optional[UserContext] = None
    ui_context: Optional[UIContext] = None
    conversation_history: list[ConversationTurn] = []
    schema_hints: Optional[SchemaHints] = None
    payload: dict[str, Any]             # service-specific, validated in service layer


class InteractiveElement(BaseModel):
    """Single interactive element extracted from page DOM."""
    model_config = ConfigDict(extra="ignore")  # allow future fields
    tag: str
    role: str
    name: str = ""
    type: str = ""
    testid: str = ""
    id: str = ""
    forLabel: str = ""


class GenerateTestCasesPayload(BaseModel):
    """Validated payload for generate_test_cases task."""
    model_config = ConfigDict(extra="forbid")
    url: str
    snapshot_text: Optional[str] = None
    interactive_elements: Optional[List[InteractiveElement]] = None
    page_title: Optional[str] = None
    locator_source: Literal["snapshot", "inferred"] = "inferred"


class GeneratePlaywrightScriptPayload(BaseModel):
    """Validated payload for generate_playwright_script task."""
    model_config = ConfigDict(extra="forbid")
    url: str
    test_cases: List[dict]
    script_variant: str = "playwright_typescript_pom"


class WebhookRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caller_module: str
    callback_url: str
    secret: Optional[str] = None
