from typing import Optional

from pydantic import BaseModel, Field, field_validator
from src.config import settings


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    max_new_tokens: int = Field(min(80, settings.max_new_tokens), ge=1, le=settings.max_new_tokens)
    temperature: float = Field(0.7, ge=0.0, le=2.0)

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value):
        if not value.strip():
            raise ValueError("Enter a sentence or prompt.")
        return value


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
    model_loading: bool = False
    model_name: str
    max_new_tokens: int
