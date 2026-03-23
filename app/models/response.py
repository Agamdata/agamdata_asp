from pydantic import BaseModel, Field
from typing import Optional, Any
import uuid


class ResponseMeta(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


class InvokeResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_type: str
    task: str
    result: dict[str, Any]
    meta: ResponseMeta


class JobAcceptedResponse(BaseModel):
    request_id: str
    job_id: str
    status: str = "queued"
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str          # queued | running | completed | failed
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
