from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import requests

PROMPTS = {
    "short": "Explain TTFT in one sentence.",
    "medium": (
        "Explain why Time To First Token matters for interactive LLM products. "
        "Include one example from a customer support assistant."
    ),
    "long": (
        "You are helping an ML platform team improve an LLM-powered assistant. "
        "Explain the difference between TTFT, total latency, throughput, and tokens per second. "
        "Then describe three practical engineering changes that could improve perceived latency."
    ),
}


def benchmark_generate(
    url: str,
    prompt_name: str,
    prompt: str,
    request_id: int,
) -> dict[str, object]:
    started_at = time.perf_counter()
    response = requests.post(
        f"{url}/generate",
        json={"prompt": prompt, "max_new_tokens": 80, "temperature": 0.7},
        timeout=120,
    )
    wall_latency_ms = (time.perf_counter() - started_at) * 1000
    response.raise_for_status()
    payload = response.json()
    return {
        "endpoint": "generate",
        "prompt_name": prompt_name,
        "request_id": request_id,
        "wall_latency_ms": wall_latency_ms,
        **payload,
    }


def benchmark_stream(url: str, prompt_name: str, prompt: str, request_id: int) -> dict[str, object]:
    started_at = time.perf_counter()
    metrics: dict[str, object] = {}
    with requests.post(
        f"{url}/generate-stream",
        json={"prompt": prompt, "max_new_tokens": 80, "temperature": 0.7},
        stream=True,
        timeout=120,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line.removeprefix("data: "))
            if "total_latency_ms" in payload:
                metrics = payload
    wall_latency_ms = (time.perf_counter() - started_at) * 1000
    return {
        "endpoint": "generate-stream",
        "prompt_name": prompt_name,
        "request_id": request_id,
        "wall_latency_ms": wall_latency_ms,
        "text": "",
        **metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--output", default="benchmark_results/results.csv")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for prompt_name, prompt in PROMPTS.items():
        for request_id in range(args.runs):
            rows.append(benchmark_generate(args.url, prompt_name, prompt, request_id))
            rows.append(benchmark_stream(args.url, prompt_name, prompt, request_id))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with output_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} benchmark rows to {output_path}")


if __name__ == "__main__":
    main()
