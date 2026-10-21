from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

import anyio
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from plotly.offline import get_plotlyjs
from starlette.concurrency import run_in_threadpool

from api.schemas import GenerateRequest, GenerateResponse, HealthResponse
from src.config import settings
from src.generation import LLMGenerator

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


class ManagedStream(StreamingResponse):
    """Close generation and release its slot on completion, failure, or disconnect."""

    def __init__(self, stream, release):
        super().__init__(stream, media_type="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        })
        self.stream = stream
        self.release = release

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                try:
                    await run_in_threadpool(self.stream.close)
                finally:
                    self.release()


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        # Keep liveness available while the separate readiness check waits for warmup.
        warmup = (
            asyncio.create_task(asyncio.to_thread(load_generator))
            if settings.preload_model else None
        )
        try:
            yield
        finally:
            if warmup:
                await asyncio.gather(warmup, return_exceptions=True)

    app = FastAPI(
        title="Latency Lab",
        description="Live language-model inference and token-level latency measurement.",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.generator_provider = LLMGenerator
    app.state.generator = None
    app.state.model_loading = False
    app.state.model_error = False
    model_lock = Lock()
    inference_lock = Lock()

    def load_generator():
        with model_lock:
            if app.state.generator is None:
                app.state.model_loading = True
                try:
                    app.state.generator = app.state.generator_provider()
                    app.state.model_error = False
                except Exception:
                    app.state.model_error = True
                    logger.exception("Model loading failed")
                    raise HTTPException(
                        503, "The model could not load. Please try again later."
                    ) from None
                finally:
                    app.state.model_loading = False
            return app.state.generator

    def acquire_generator(request):
        if not inference_lock.acquire(blocking=False):
            raise HTTPException(
                429, "The model is busy. Please retry shortly.", headers={"Retry-After": "2"}
            )
        try:
            generator = load_generator()
            if hasattr(generator, "validate_request"):
                generator.validate_request(request.prompt, request.max_new_tokens)
            return generator
        except ValueError as error:
            inference_lock.release()
            raise HTTPException(422, str(error)) from error
        except Exception:
            inference_lock.release()
            raise

    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="frontend")

    @app.get("/", include_in_schema=False)
    def frontend():
        return FileResponse(ROOT / "frontend" / "index.html")

    @app.get("/benchmarks", include_in_schema=False)
    def benchmarks():
        return FileResponse(ROOT / "dashboard" / "index.html")

    @app.get("/assets/plotly.min.js", include_in_schema=False)
    def plotly():
        return Response(
            get_plotlyjs(), media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(
            status="ok", model_loaded=app.state.generator is not None,
            model_loading=app.state.model_loading, model_name=settings.model_name,
            max_new_tokens=settings.max_new_tokens,
        )

    @app.get("/ready")
    def ready():
        loaded = app.state.generator is not None
        state = (
            "ready" if loaded else "error" if app.state.model_error
            else "loading" if app.state.model_loading else "not_loaded"
        )
        return JSONResponse(
            {"status": state, "model_loaded": loaded}, status_code=200 if loaded else 503
        )

    @app.post("/generate", response_model=GenerateResponse)
    def generate(request: GenerateRequest):
        generator = acquire_generator(request)
        try:
            return GenerateResponse(**generator.generate(
                request.prompt, request.max_new_tokens, request.temperature
            ))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except Exception:
            logger.exception("Generation failed")
            raise HTTPException(
                503, "Generation failed. Please retry with a shorter prompt."
            ) from None
        finally:
            inference_lock.release()

    @app.post("/generate-stream")
    def generate_stream(request: GenerateRequest):
        generator = acquire_generator(request)
        try:
            stream = generator.stream(
                request.prompt, request.max_new_tokens, request.temperature
            )
            return ManagedStream(stream, inference_lock.release)
        except Exception:
            inference_lock.release()
            raise

    return app


app = create_app()
