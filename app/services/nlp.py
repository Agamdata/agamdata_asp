"""
ASP-01 NLP Service

Supported tasks:
- nl_to_sql
- intent_extraction
- entity_recognition
- sentiment
- language_detection
"""
import json
from typing import Optional

import structlog
from fastapi import HTTPException
from pydantic import BaseModel

from app.models.request import ConversationTurn, InvokeRequest
from app.models.response import InvokeResponse
from app.registry import prompt_registry, context_store
from app.services._shared import anthropic_client, build_messages, build_invoke_response, strip_json
from app.services import rag
from app.services.rag import format_chunks

log = structlog.get_logger()

VALID_TASKS = {"nl_to_sql", "intent_extraction", "entity_recognition", "sentiment", "language_detection"}


# --- Output schemas ---

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


async def handle(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    if req.task not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown nlp task: {req.task}")

    log.info("nlp_invoke_start", request_id=request_id, tenant_id=req.tenant_id,
             caller_module=req.caller_module, task=req.task, model=model)

    if req.task == "nl_to_sql":
        return await _handle_nl_to_sql(req, model, request_id)
    else:
        return await _handle_generic(req, model, request_id)


async def _handle_nl_to_sql(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    query_text = req.payload.get("query")
    if not query_text:
        raise HTTPException(status_code=400, detail="payload.query is required for nl_to_sql")

    # Step 1: Retrieve schema context from RAG (ASP-02)
    schema_chunks = await rag.retrieve(
        query=query_text,
        tenant_id=req.tenant_id,
        primary_entity=req.schema_hints.primary_entity if req.schema_hints else None,
        exclude_tables=req.schema_hints.exclude_tables if req.schema_hints else [],
        top_k=8,
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

    # Step 5: Call Claude
    response = await anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
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


async def _handle_generic(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    maturity = req.user_context.maturity_level if req.user_context else "L2"
    prompt = await prompt_registry.get_prompt("nlp", req.task, req.caller_module, maturity)

    user_message = prompt.user_prompt_template.format(**req.payload)
    response = await anthropic_client.messages.create(
        model=model,
        max_tokens=512,
        system=prompt.system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    raw = response.content[0].text

    schema_cls = TASK_OUTPUT_SCHEMAS.get(req.task)
    try:
        output = schema_cls.model_validate_json(strip_json(raw))
    except Exception as e:
        log.error("nlp_parse_failed", request_id=request_id, task=req.task, error=str(e))
        raise HTTPException(status_code=500, detail={"detail": "Internal error", "request_id": request_id})

    return build_invoke_response(request_id, "nlp", req.task, output, response.usage, model)
