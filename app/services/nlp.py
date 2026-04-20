"""
ASP-01 NLP Service

Supported tasks:
- nl_to_sql          (uses RAG — ASP-02)
- intent_extraction
- entity_recognition
- sentiment
- language_detection
- classify_probe_result  (NEW — ASP-FEAT-ASP-01 v1.2)
"""
import json
import time
from typing import Optional

import structlog
from fastapi import HTTPException
from pydantic import BaseModel

from app.models.request import ConversationTurn, InvokeRequest
from app.models.response import InvokeResponse
from app.registry import prompt_registry, context_store
from app.schemas.nlp_schemas import (
    ClassifyProbeResultPayload,
    ClassifyProbeResultOutput,
    SuggestScreenMappingPayload,
    SuggestScreenMappingResult,
)
from app.services._shared import anthropic_client, build_messages, build_invoke_response, strip_json
from app.services import rag
from app.services.rag import format_chunks, RAGCollectionMissingError
from app.utils.json_parser import extract_json, LLMParseError
from app.utils.llm_retry import llm_call_with_retry

log = structlog.get_logger()

VALID_TASKS = {
    "nl_to_sql",
    "intent_extraction",
    "entity_recognition",
    "sentiment",
    "language_detection",
    "classify_probe_result",
    "suggest_screen_mapping",   # PAP-ASP-REQ-ASP-01 v2.0 / BP-10 (ASP-OUT-020)
    "extract_test_entities",    # F-03-02 / PAP-ASP-REQ-ASP-02 v1.0 (ASP-OUT-036, migration 027)
}


# --- Output schemas (existing tasks) ---

class NLtoSQLOutput(BaseModel):
    sql: str
    explanation: str
    tables_used: list[str]
    confidence: float
    ambiguities: list[str] = []


class IntentExtractionOutput(BaseModel):
    intent: str
    entities: dict
    confidence: float


class EntityRecognitionOutput(BaseModel):
    entities: list[dict]


class SentimentOutput(BaseModel):
    sentiment: str
    score: float


class LanguageDetectionOutput(BaseModel):
    language: str
    confidence: float


TASK_OUTPUT_SCHEMAS = {
    "nl_to_sql": NLtoSQLOutput,
    "intent_extraction": IntentExtractionOutput,
    "entity_recognition": EntityRecognitionOutput,
    "sentiment": SentimentOutput,
    "language_detection": LanguageDetectionOutput,
}

# suggest_screen_mapping (BP-10) uses dedicated handler with hallucination
# guard — NOT registered in the generic TASK_OUTPUT_SCHEMAS map because
# the dispatch in handle() branches explicitly to _handle_suggest_screen_mapping.


async def handle(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    if req.task not in VALID_TASKS:
        raise HTTPException(status_code=422, detail=f"Unknown task: '{req.task}'")

    log.info("nlp_invoke_start", request_id=request_id, tenant_id=req.tenant_id,
             caller_module=req.caller_module, task=req.task, model=model)

    if req.task == "nl_to_sql":
        return await _handle_nl_to_sql(req, model, request_id)
    elif req.task == "classify_probe_result":
        return await _handle_classify_probe_result(req, model, request_id)
    elif req.task == "suggest_screen_mapping":
        return await _handle_suggest_screen_mapping(req, model, request_id)
    else:
        return await _handle_generic(req, model, request_id)


async def _handle_nl_to_sql(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    query_text = req.payload.get("query")
    if not query_text:
        raise HTTPException(status_code=422, detail="payload.query is required for nl_to_sql")

    # Step 1: Retrieve schema context from RAG (ASP-02)
    # I-RAG-07 (ASP-OUT-026): missing-collection is fail-CLOSED → 503.
    # Empty-retrieve (collection exists, zero matches) is fail-OPEN and
    # flows through as an empty list — LLM proceeds with empty
    # schema_context and may return a lower-confidence answer. See
    # ASP-FEAT-ASP-02 v1.0 §8.2.
    try:
        schema_chunks = await rag.retrieve(
            query=query_text,
            tenant_id=req.tenant_id,
            primary_entity=req.schema_hints.primary_entity if req.schema_hints else None,
            exclude_tables=req.schema_hints.exclude_tables if req.schema_hints else [],
            top_k=8,
        )
    except RAGCollectionMissingError as e:
        log.error(
            "rag_collection_missing",
            tenant_id=req.tenant_id,
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "type": "/errors/rag-collection-missing",
                "title": "Schema ontology not available for this tenant",
                "detail": "Schema context unavailable. Ontology sync required.",
                "request_id": request_id,
                "remediation": "admin ontology_sync required",
            },
        )

    # Step 2: Fetch prompt from registry
    maturity = req.user_context.maturity_level if req.user_context else "L2"
    prompt = await prompt_registry.get_prompt("nlp", "nl_to_sql", req.caller_module, maturity)

    # Step 3: Load conversation history
    history = req.conversation_history
    if not history and req.session_id:
        history = await context_store.get_context(req.tenant_id, req.caller_module, req.session_id)

    # Step 4: Build messages
    system = prompt.system_prompt.format(
        schema_context=format_chunks(schema_chunks),
        active_filters=json.dumps(req.ui_context.active_filters if req.ui_context else {}),
        user_role=req.user_context.role if req.user_context else "user",
        exclude_tables=",".join(req.schema_hints.exclude_tables if req.schema_hints else []),
    )
    messages = build_messages(history, query_text)

    # Step 5: Call Claude (DEFECT-016: 529 retry via shared utility)
    response = await llm_call_with_retry(
        anthropic_client,
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
        request_id=request_id,
    )
    raw = response.content[0].text

    # Step 6: Parse structured output
    try:
        output = NLtoSQLOutput.model_validate_json(strip_json(raw))
    except Exception as e:
        log.error("nlp_parse_failed", request_id=request_id, error=str(e), raw=raw[:200])
        raise HTTPException(status_code=500, detail={"detail": "Internal error", "request_id": request_id})

    # Step 7: Update context store if session_id provided
    if req.session_id:
        updated = list(history) + [
            ConversationTurn(role="user", content=query_text, turn=len(history) + 1),
            ConversationTurn(
                role="assistant",
                content=output.explanation,
                generated_sql=output.sql,
                turn=len(history) + 2,
            ),
        ]
        await context_store.set_context(req.tenant_id, req.caller_module, req.session_id, updated)

    return build_invoke_response(request_id, "nlp", "nl_to_sql", output, response.usage, model)


async def _handle_classify_probe_result(
    req: InvokeRequest, model: str, request_id: str
) -> InvokeResponse:
    """Handle classify_probe_result task (ASP-FEAT-ASP-01 v1.2, Section 11.6).

    1. Validate payload via ClassifyProbeResultPayload
    2. Defensive log if visible_text > 2000 chars [v1.2 M-2]
    3. Lookup prompt from ASP-06
    4. Build prompt with variable substitution (None → 'N/A')
    5. Call LLM via Anthropic
    6. Parse JSON via extract_json() (ADR-025)
    7. Validate → ClassifyProbeResultOutput
    """
    # Validate payload
    try:
        payload = ClassifyProbeResultPayload(**req.payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Validation error: {str(e)}")

    # [v1.2 M-2] Defensive warning if visible_text exceeds caller contract limit
    if len(payload.visible_text) > 2000:
        log.warning(
            "visible_text_exceeds_limit",
            request_id=request_id,
            tenant_id=req.tenant_id,
            caller_module=req.caller_module,
            actual_length=len(payload.visible_text),
            limit=2000,
        )

    # Step 1: Lookup prompt from ASP-06
    prompt = await prompt_registry.get_prompt(
        "nlp", "classify_probe_result", req.caller_module, "*"
    )

    # Step 2: Build prompt with variable substitution
    # None values rendered as 'N/A' per spec Section 11.6
    user_message = prompt.user_prompt_template.format(
        page_url=payload.page_url,
        page_type=payload.page_type,
        submitted_fields=json.dumps(payload.submitted_fields),
        post_submit_url=payload.post_submit_url or "N/A",
        post_submit_status=payload.post_submit_status if payload.post_submit_status is not None else "N/A",
        visible_text=payload.visible_text,
    )

    # Step 3: Call Claude via ASP-11 Model Router (DEFECT-016: 529 retry)
    response = await llm_call_with_retry(
        anthropic_client,
        model=model,
        max_tokens=512,
        system=prompt.system_prompt,
        messages=[{"role": "user", "content": user_message}],
        request_id=request_id,
    )
    raw = response.content[0].text

    # Step 4: Parse JSON via extract_json() (ADR-025)
    try:
        parsed = extract_json(raw)
        output = ClassifyProbeResultOutput(**parsed)
    except LLMParseError as e:
        log.error(
            "nlp_parse_failed",
            request_id=request_id,
            task="classify_probe_result",
            error=str(e),
            raw=raw[:200],
        )
        raise HTTPException(
            status_code=500,
            detail={"detail": "Internal error", "request_id": request_id},
        )
    except Exception as e:
        log.error(
            "nlp_validation_failed",
            request_id=request_id,
            task="classify_probe_result",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={"detail": "Internal error", "request_id": request_id},
        )

    return build_invoke_response(
        request_id, "nlp", "classify_probe_result", output, response.usage, model
    )


async def _handle_suggest_screen_mapping(
    req: InvokeRequest, model: str, request_id: str
) -> InvokeResponse:
    """Handle suggest_screen_mapping task (PAP-ASP-REQ-ASP-01 v2.0 / BP-10).

    Maps a page (URL + title + type) to the best-matching internal module
    from a caller-supplied list. LLM returns a module_key; handler verifies
    it's in the allowed list (hallucination guard per AC-BP10-03).
    """
    # Payload validation
    try:
        payload = SuggestScreenMappingPayload(**req.payload)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid payload for suggest_screen_mapping: {e}",
        )

    allowed_keys = {m.module_key for m in payload.available_modules}

    # Fetch prompt — use get_prompt for 4-level fallback chain; ab_variant is NULL for this task
    maturity = req.user_context.maturity_level if req.user_context else "L2"
    prompt = await prompt_registry.get_prompt(
        "nlp", "suggest_screen_mapping", req.caller_module, maturity
    )

    # Render available_modules as newline-separated "key: name" list for the prompt
    modules_rendered = "\n".join(
        f"  - {m.module_key}: {m.module_name}" for m in payload.available_modules
    )

    user_message = prompt.user_prompt_template.format(
        page_url=payload.page_url,
        page_title=payload.page_title or "(not provided)",
        page_type=payload.page_type or "(not provided)",
        available_modules=modules_rendered,
    )

    # LLM call — standard tier (Haiku) per directive
    response = await llm_call_with_retry(
        anthropic_client,
        model=model,
        max_tokens=512,           # compact response — just 3 fields
        system=prompt.system_prompt,
        messages=[{"role": "user", "content": user_message}],
        request_id=request_id,
    )
    raw = response.content[0].text

    # Parse output → SuggestScreenMappingResult
    try:
        output = SuggestScreenMappingResult.model_validate_json(strip_json(raw))
    except Exception as e:
        log.error(
            "nlp_parse_failed",
            request_id=request_id,
            task="suggest_screen_mapping",
            error=str(e),
            raw=raw[:500],
        )
        raise HTTPException(
            status_code=500,
            detail={"detail": "Internal error", "request_id": request_id},
        )

    # Hallucination guard (AC-BP10-03) — if LLM returned a key not in
    # allowed_keys, scrub the output to safe defaults and log.
    if output.suggested_module_key is not None and output.suggested_module_key not in allowed_keys:
        log.warning(
            "hallucinated_module_key",
            request_id=request_id,
            task="suggest_screen_mapping",
            caller_feature=req.caller_feature,
            hallucinated_key=output.suggested_module_key,
            allowed_keys=sorted(allowed_keys),
        )
        output = SuggestScreenMappingResult(
            suggested_module_key=None,
            suggested_screen_name=None,
            confidence=0.0,
        )

    return build_invoke_response(
        request_id, "nlp", "suggest_screen_mapping", output, response.usage, model
    )


async def _handle_generic(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    maturity = req.user_context.maturity_level if req.user_context else "L2"
    prompt = await prompt_registry.get_prompt("nlp", req.task, req.caller_module, maturity)

    user_message = prompt.user_prompt_template.format(**req.payload)
    response = await llm_call_with_retry(
        anthropic_client,
        model=model,
        max_tokens=512,
        system=prompt.system_prompt,
        messages=[{"role": "user", "content": user_message}],
        request_id=request_id,
    )
    raw = response.content[0].text

    schema_cls = TASK_OUTPUT_SCHEMAS.get(req.task)
    try:
        output = schema_cls.model_validate_json(strip_json(raw))
    except Exception as e:
        log.error("nlp_parse_failed", request_id=request_id, task=req.task, error=str(e))
        raise HTTPException(status_code=500, detail={"detail": "Internal error", "request_id": request_id})

    return build_invoke_response(request_id, "nlp", req.task, output, response.usage, model)
