"""
ASP-13 Dashboard Intelligence Service

Supported tasks:
- interpret_chart      (structured or screenshot mode)
- narrate_dashboard    (structured or screenshot mode)
- detect_anomaly       (structured)
- suggest_drilldown    (structured)
"""
import json
import structlog
from fastapi import HTTPException
from pydantic import BaseModel

from app.models.request import InvokeRequest
from app.models.response import InvokeResponse
from app.registry import prompt_registry
from app.services._shared import anthropic_client, build_invoke_response, strip_json

log = structlog.get_logger()

VALID_TASKS = {"interpret_chart", "narrate_dashboard", "detect_anomaly", "suggest_drilldown"}


class DashboardOutput(BaseModel):
    insight: str
    anomalies: list[dict] = []
    suggested_actions: list[str] = []
    confidence: float = 1.0


async def handle(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    if req.task not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown dashboard_intelligence task: {req.task}")

    log.info("dashboard_invoke_start", request_id=request_id, tenant_id=req.tenant_id,
             caller_module=req.caller_module, task=req.task, model=model)

    input_mode = req.payload.get("input_mode", "structured")
    if input_mode == "screenshot":
        return await _handle_screenshot_mode(req, model, request_id)
    else:
        return await _handle_structured_mode(req, model, request_id)


async def _handle_screenshot_mode(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    image_data = req.payload.get("image_data")
    if not image_data:
        raise HTTPException(status_code=400, detail="payload.image_data required for screenshot mode")

    image_mime = req.payload.get("image_mime", "image/png")
    query = req.payload.get("query", "Interpret this dashboard chart.")

    response = await anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        system="You are a CRM data analyst. Interpret the chart image provided.",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_mime,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": query},
                ],
            }
        ],
    )

    return build_invoke_response(
        request_id,
        "dashboard_intelligence",
        req.task,
        {"insight": response.content[0].text},
        response.usage,
        model,
    )


async def _handle_structured_mode(req: InvokeRequest, model: str, request_id: str) -> InvokeResponse:
    maturity = req.user_context.maturity_level if req.user_context else "L2"
    prompt = await prompt_registry.get_prompt(
        "dashboard_intelligence", req.task, req.caller_module, maturity
    )

    chart_json = json.dumps(req.payload.get("chart_context", {}))
    dashboard_json = json.dumps(req.payload.get("dashboard_context", {}))

    user_msg = prompt.user_prompt_template.format(
        query=req.payload.get("query", ""),
        chart_context=chart_json,
        dashboard_context=dashboard_json,
    )

    response = await anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        system=prompt.system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text
    try:
        output = DashboardOutput.model_validate_json(strip_json(raw))
    except Exception as e:
        log.error("dashboard_parse_failed", request_id=request_id, task=req.task, error=str(e))
        raise HTTPException(status_code=500, detail={"detail": "Internal error", "request_id": request_id})

    return build_invoke_response(
        request_id,
        "dashboard_intelligence",
        req.task,
        output.model_dump(),
        response.usage,
        model,
    )
