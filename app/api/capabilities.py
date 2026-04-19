"""
ASP Capabilities & Schema Discovery Endpoints (ADR-030)

Zone 2 Shared Contract surface. Consumers can query supported tasks
and payload schemas at runtime.

Spec: ASP-FEAT-ASP-03 v1.1, Section 4.1
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.gateway.auth import verify_api_key

router = APIRouter()


# ---------------------------------------------------------------------------
# VALID_TASKS aggregation from each service (I-CAP-03)
# Imported at module level — if a service fails to import, startup crashes
# loudly rather than silently omitting it from capabilities.
# ---------------------------------------------------------------------------

from app.services.nlp import VALID_TASKS as NLP_TASKS
from app.services.generation import VALID_TASKS as GENERATION_TASKS

# Map service_type → sorted task list
SERVICE_CAPABILITIES: dict[str, list[str]] = {
    "nlp": sorted(NLP_TASKS),
    "generation": sorted(GENERATION_TASKS),
}

# Map (service_type, task) → Pydantic payload model for JSON schema export
TASK_SCHEMA_MODELS: dict[tuple[str, str], type[BaseModel]] = {}

# Register generation payload schemas
from app.schemas.generation_schemas import (
    GenerateTestCasesPayload,
    GenerateTestCasesWithInventoryPayload,
    GeneratePlaywrightScriptPayload,
    RefactorScriptLocatorsPayload,          # v2.0 (I-024-07)
)

TASK_SCHEMA_MODELS[("generation", "generate_test_cases")] = GenerateTestCasesPayload
TASK_SCHEMA_MODELS[("generation", "generate_test_cases_with_inventory")] = GenerateTestCasesWithInventoryPayload
TASK_SCHEMA_MODELS[("generation", "generate_playwright_script")] = GeneratePlaywrightScriptPayload
TASK_SCHEMA_MODELS[("generation", "refactor_script_locators")] = RefactorScriptLocatorsPayload   # v2.0

# Register NLP payload schemas
from app.schemas.nlp_schemas import (
    NlToSqlPayload,
    IntentExtractPayload,
    EntityRecognitionPayload,
    SentimentAnalysisPayload,
    ClassifyProbeResultPayload,
)

TASK_SCHEMA_MODELS[("nlp", "nl_to_sql")] = NlToSqlPayload
TASK_SCHEMA_MODELS[("nlp", "intent_extract")] = IntentExtractPayload
TASK_SCHEMA_MODELS[("nlp", "entity_recognition")] = EntityRecognitionPayload
TASK_SCHEMA_MODELS[("nlp", "sentiment_analysis")] = SentimentAnalysisPayload
TASK_SCHEMA_MODELS[("nlp", "classify_probe_result")] = ClassifyProbeResultPayload


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CapabilitiesResponse(BaseModel):
    services: dict[str, list[str]]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/ai/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(tenant=Depends(verify_api_key)):
    """List all supported services and their tasks (ADR-030).

    Auth required (§S-7). Intentionally does NOT include migration_head
    per Architect ruling 2026-04-17 — migration head is Zone 1 / operational,
    not a Zone 2 consumer surface.
    """
    return CapabilitiesResponse(services=SERVICE_CAPABILITIES)


@router.get("/ai/schemas/{service_type}/{task}")
async def get_task_schema(
    service_type: str,
    task: str,
    tenant=Depends(verify_api_key),
):
    """Return JSON Schema for a specific task's payload model (ADR-030).

    Auth required (§S-7). Returns the Pydantic model's JSON Schema via
    model_json_schema(). 422 if service_type/task not in capabilities.
    """
    model = TASK_SCHEMA_MODELS.get((service_type, task))
    if model is None:
        supported = SERVICE_CAPABILITIES.get(service_type)
        if supported is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown service '{service_type}'. Supported: {sorted(SERVICE_CAPABILITIES.keys())}",
            )
        raise HTTPException(
            status_code=422,
            detail=f"Unknown task '{task}'. Supported for {service_type}: {supported}",
        )
    return model.model_json_schema()
