from __future__ import annotations

import json
import logging
import time
from threading import Thread
from typing import Dict, Generator, Optional

import torch
from transformers import TextIteratorStreamer

from src.config import settings
from src.metrics import LatencyMetrics
from src.model_loader import load_model_and_tokenizer

logger = logging.getLogger(__name__)


class TimedStreamer(TextIteratorStreamer):
    """Observe generated token IDs before the text streamer's word buffering."""

    def __init__(self, tokenizer) -> None:
        super().__init__(tokenizer, skip_prompt=True, skip_special_tokens=True)
        self.first_token_at: Optional[float] = None
        self.output_tokens = 0

    def put(self, value) -> None:
        value = value.cpu()
        if not self.next_tokens_are_prompt and value.numel():
            if self.first_token_at is None:
                self.first_token_at = time.perf_counter()
            self.output_tokens += value.numel()
        super().put(value)


class LLMGenerator:
    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.model_name
        self.model, self.tokenizer, self.device = load_model_and_tokenizer(self.model_name)

    def _inputs(self, prompt: str) -> Dict[str, torch.Tensor]:
        return self.tokenizer(prompt, return_tensors="pt").to(self.device)

    def _synchronize(self) -> None:
        if str(self.device).startswith("cuda"):
            torch.cuda.synchronize(self.device)
        elif str(self.device) == "mps":
            torch.mps.synchronize()

    def generate(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
    ) -> dict[str, object]:
        inputs = self._inputs(prompt)
        streamer = TimedStreamer(self.tokenizer)
        self._synchronize()
        started_at = time.perf_counter()
        with torch.inference_mode():
            generation_kwargs = {
                **inputs,
                "streamer": streamer,
                "max_new_tokens": max_new_tokens,
                "do_sample": temperature > 0,
                "pad_token_id": self.tokenizer.eos_token_id,
            }
            if temperature > 0:
                generation_kwargs["temperature"] = temperature
            outputs = self.model.generate(**generation_kwargs)
        self._synchronize()
        total_latency_ms = (time.perf_counter() - started_at) * 1000

        input_tokens = int(inputs["input_ids"].shape[-1])
        output_tokens = int(outputs.shape[-1] - input_tokens)
        generated_text = self.tokenizer.decode(outputs[0, input_tokens:], skip_special_tokens=True)
        metrics = LatencyMetrics(
            input_tokens=input_tokens,
            output_tokens=max(output_tokens, 0),
            total_latency_ms=total_latency_ms,
            ttft_ms=(streamer.first_token_at - started_at) * 1000
            if streamer.first_token_at is not None else None,
        )

        return {
            "text": generated_text,
            "model_name": self.model_name,
            "device": self.device,
            **metrics.to_dict(),
        }

    def stream(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
    ) -> Generator[str, None, None]:
        inputs = self._inputs(prompt)
        input_tokens = int(inputs["input_ids"].shape[-1])
        streamer = TimedStreamer(self.tokenizer)

        generation_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": max_new_tokens,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            generation_kwargs["temperature"] = temperature

        chunks: list[str] = []
        errors: list[Exception] = []
        finished_at: Optional[float] = None

        def run_generation() -> None:
            nonlocal finished_at
            try:
                with torch.inference_mode():
                    self.model.generate(**generation_kwargs)
                self._synchronize()
            except Exception as exc:
                logger.exception("Model generation failed")
                errors.append(exc)
                # Unblock the consumer even when model generation fails.
                streamer.on_finalized_text("", stream_end=True)
            finally:
                finished_at = time.perf_counter()

        self._synchronize()
        started_at = time.perf_counter()
        thread = Thread(target=run_generation, daemon=True)
        thread.start()

        for chunk in streamer:
            if not chunk:
                continue
            chunks.append(chunk)
            yield _sse("token", {"text": chunk})

        thread.join()
        if errors:
            yield _sse("error", {"message": "Model generation failed. Check the server logs."})
            return
        assert finished_at is not None
        total_latency_ms = (finished_at - started_at) * 1000
        ttft_ms = (
            (streamer.first_token_at - started_at) * 1000
            if streamer.first_token_at is not None else None
        )
        metrics = LatencyMetrics(
            input_tokens=input_tokens,
            output_tokens=streamer.output_tokens,
            ttft_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
        )

        yield _sse(
            "metrics",
            {
                "text": "".join(chunks),
                "model_name": self.model_name,
                "device": self.device,
                **metrics.to_dict(),
            },
        )


def _sse(event: str, data: Dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
