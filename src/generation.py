from __future__ import annotations

import json
import time
from threading import Thread
from typing import Dict, Generator, Optional

import torch
from transformers import TextIteratorStreamer

from src.config import settings
from src.metrics import LatencyMetrics
from src.model_loader import load_model_and_tokenizer


class LLMGenerator:
    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.model_name
        self.model, self.tokenizer, self.device = load_model_and_tokenizer(self.model_name)

    def _inputs(self, prompt: str) -> Dict[str, torch.Tensor]:
        return self.tokenizer(prompt, return_tensors="pt").to(self.device)

    def generate(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
    ) -> dict[str, object]:
        inputs = self._inputs(prompt)
        started_at = time.perf_counter()
        with torch.inference_mode():
            generation_kwargs = {
                **inputs,
                "max_new_tokens": max_new_tokens,
                "do_sample": temperature > 0,
                "pad_token_id": self.tokenizer.eos_token_id,
            }
            if temperature > 0:
                generation_kwargs["temperature"] = temperature
            outputs = self.model.generate(**generation_kwargs)
        total_latency_ms = (time.perf_counter() - started_at) * 1000

        input_tokens = int(inputs["input_ids"].shape[-1])
        output_tokens = int(outputs.shape[-1] - input_tokens)
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        generated_text = text[len(prompt) :].strip() if text.startswith(prompt) else text
        metrics = LatencyMetrics(
            input_tokens=input_tokens,
            output_tokens=max(output_tokens, 0),
            total_latency_ms=total_latency_ms,
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
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        generation_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": max_new_tokens,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            generation_kwargs["temperature"] = temperature

        started_at = time.perf_counter()
        first_token_at: Optional[float] = None
        chunks: list[str] = []

        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        for chunk in streamer:
            if not chunk:
                continue
            if first_token_at is None:
                first_token_at = time.perf_counter()
            chunks.append(chunk)
            yield _sse("token", {"text": chunk})

        thread.join()
        finished_at = time.perf_counter()
        total_latency_ms = (finished_at - started_at) * 1000
        ttft_ms = ((first_token_at or finished_at) - started_at) * 1000
        output_tokens = len(self.tokenizer.encode("".join(chunks), add_special_tokens=False))
        metrics = LatencyMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            ttft_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
        )

        yield _sse(
            "metrics",
            {
                "model_name": self.model_name,
                "device": self.device,
                **metrics.to_dict(),
            },
        )


def _sse(event: str, data: Dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
