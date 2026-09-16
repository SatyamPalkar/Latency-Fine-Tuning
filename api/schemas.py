from typing import Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    max_new_tokens: int = Field(80, ge=1, le=256)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    text: str
    model_name: str
    device: str
    input_tokens: int
    output_tokens: int
    ttft_ms: Optional[float]
    total_latency_ms: float
    tokens_per_second: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
