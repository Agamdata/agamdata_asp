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
    placeholder: str = ""
    testid: str = ""
    id: str = ""
    forLabel: str = ""


class GenerateTestCasesPayload(BaseModel):
    """Validated payload for generate_test_cases task."""
    model_config = ConfigDict(extra="ignore")   # caller may send metadata fields; ignore unknown
    url: str
    snapshot_text: Optional[str] = None
    interactive_elements: Optional[List[InteractiveElement]] = None
    page_title: Optional[str] = None
    locator_source: Literal["snapshot", "inferred"] = "inferred"


class GeneratePlaywrightScriptPayload(BaseModel):
    """Validated payload for generate_playwright_script task."""
    model_config = ConfigDict(extra="ignore")   # caller may send metadata fields; ignore unknown
    url: str
    test_cases: List[dict]
    script_variant: str = "playwright_typescript_pom"
    # Title format fields sent by script_generator.py (v1.1) — declared
    # explicitly for documentation; extra fields are ignored anyway.
    title_format: Optional[str] = None          # e.g. '[{tc_id}] {test_name}'
    title_format_example: Optional[str] = None  # e.g. '[TC-PI-001] Create invoice ...'


class LocatorInventoryLocators(BaseModel):
    """Verified locator set for one inventory element."""
    model_config = ConfigDict(extra="ignore")
    recommended: str                    # verbatim Playwright call — LLM must copy this
    all_verified: dict[str, str] = {}   # every strategy that resolved to exactly 1 element
    is_fragile: bool = False            # true when recommended is css_fallback only


class LocatorInventoryItem(BaseModel):
    """One element entry in the verified locator inventory."""
    model_config = ConfigDict(extra="ignore")
    element_name: str                   # snake_case identifier, e.g. email_input
    tag: str                            # HTML tag: input | button | a | select | textarea
    type: str = ""                      # input type attr; empty for buttons/links
    label_text: str = ""               # text from <label> or aria-label; empty if none
    placeholder: str = ""              # placeholder attr value; empty if none
    button_text: str = ""              # visible text of button/link (trimmed to 80 chars)
    is_visible: bool = True            # element has non-zero bounding box on page
    locators: LocatorInventoryLocators


class GenerateTestCasesWithInventoryPayload(BaseModel):
    """Validated payload for generate_test_cases_with_inventory task."""
    model_config = ConfigDict(extra="ignore")   # caller may send metadata fields; ignore unknown
    url: str
    page_title: Optional[str] = None
    locator_source: Literal["verified"] = "verified"
    locator_inventory: List[LocatorInventoryItem]


class WebhookRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caller_module: str
    callback_url: str
    secret: Optional[str] = None
