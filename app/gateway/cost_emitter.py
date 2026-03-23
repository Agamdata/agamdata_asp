from app.cost.meter import emit_cost_event


async def emit_cost_event_from_gateway(
    *,
    request_id: str,
    tenant_id,
    caller_module: str,
    service_type: str,
    task: str,
    model: str,
    quality_tier: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: int,
    status: str = "success",
    error_message: str = None,
) -> None:
    await emit_cost_event(
        request_id=request_id,
        tenant_id=str(tenant_id),
        caller_module=caller_module,
        service_type=service_type,
        task=task,
        model=model,
        quality_tier=quality_tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
    )
