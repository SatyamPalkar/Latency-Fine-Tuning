from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from plotly.offline import get_plotlyjs

from api.schemas import GenerateRequest, GenerateResponse, HealthResponse
from src.generation import LLMGenerator

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def plotly_bundle() -> str:
    return get_plotlyjs()


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
    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="frontend")

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(ROOT / "frontend" / "index.html")

    @app.get("/benchmarks", include_in_schema=False)
    def benchmarks() -> FileResponse:
        return FileResponse(ROOT / "dashboard" / "index.html")

    @app.get("/assets/plotly.min.js", include_in_schema=False)
    def plotly() -> Response:
        return Response(
            plotly_bundle(), media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=86400"},
        )

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
