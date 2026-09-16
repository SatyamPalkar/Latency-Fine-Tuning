from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from api.schemas import GenerateRequest, GenerateResponse, HealthResponse
from src.generation import LLMGenerator


@lru_cache(maxsize=1)
def get_generator() -> LLMGenerator:
    return LLMGenerator()


def create_app() -> FastAPI:
    app = FastAPI(
        title="LLM TTFT Optimization Platform",
        description="FastAPI service for measuring LLM latency and Time To First Token.",
        version="0.1.0",
    )
    app.state.generator_provider = get_generator

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", model_loaded=True)

    @app.post("/generate", response_model=GenerateResponse)
    def generate(request: GenerateRequest) -> GenerateResponse:
        generator = app.state.generator_provider()
        result = generator.generate(
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
        )
        return GenerateResponse(**result)

    @app.post("/generate-stream")
    def generate_stream(request: GenerateRequest) -> StreamingResponse:
        generator = app.state.generator_provider()
        stream = generator.stream(
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
        )
        return StreamingResponse(stream, media_type="text/event-stream")

    return app


app = create_app()
