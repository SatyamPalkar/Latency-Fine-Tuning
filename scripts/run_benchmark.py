"""Serial warmed HTTP benchmarks with raw rows, failures, and provenance."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {
    "short": "A good data pipeline should",
    "medium": "A language model generates text one token at a time. In an interactive application, the delay before the first generated token matters because",
    "long": "When evaluating an interactive language model, an engineering team records the time to first token, total generation time, and output tokens per second. The team compares identical prompts on the same device, separates model loading from decoding, and repeats each request after warmup. These measurements help the team understand",
}
METRICS = ["ttft_ms", "total_latency_ms", "tokens_per_second", "wall_latency_ms", "client_first_text_ms"]


def sse_events(lines):
    """Parse comments, multiline data, CRLF, named events, and a final frame."""
    event, data = "message", []
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        line = line.rstrip("\r")
        if not line:
            if data:
                yield event, json.loads("\n".join(data))
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield event, json.loads("\n".join(data))


def validate_metrics(payload):
    if not isinstance(payload, dict):
        raise ValueError("Metrics must be an object")
    for name in ["input_tokens", "output_tokens", "total_latency_ms", "tokens_per_second"]:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"Missing or invalid metric: {name}")
    ttft = payload.get("ttft_ms")
    if ttft is not None and (isinstance(ttft, bool) or not isinstance(ttft, (int, float)) or not math.isfinite(ttft) or not 0 <= ttft <= payload["total_latency_ms"]):
        raise ValueError("Invalid server TTFT")
    if payload["output_tokens"] > 0 and ttft is None:
        raise ValueError("Generated tokens require a measured TTFT")
    if not payload.get("model_name") or not payload.get("device"):
        raise ValueError("Missing model or device metadata")
    return payload


def measure(session, url, endpoint, payload, timeout):
    start = time.perf_counter()
    first_text = None
    if endpoint == "generate":
        with session.post(f"{url}/{endpoint}", json=payload, timeout=timeout) as response:
            response.raise_for_status()
            metrics = response.json()
    else:
        metrics = None
        with session.post(f"{url}/{endpoint}", json=payload, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            response.encoding = "utf-8"
            for event, data in sse_events(response.iter_lines(chunk_size=1, decode_unicode=True)):
                if event == "error":
                    raise ValueError(data.get("message", "Stream failed"))
                if event == "token" and data.get("text") and first_text is None:
                    first_text = (time.perf_counter() - start) * 1000
                if event == "metrics":
                    if metrics is not None:
                        raise ValueError("Duplicate final metrics event")
                    metrics = data
        if metrics is None:
            raise ValueError("Stream ended without final metrics")
    wall = (time.perf_counter() - start) * 1000
    return {**validate_metrics(metrics), "wall_latency_ms": wall, "client_first_text_ms": first_text}


def percentile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lower, upper = int(index), min(int(index) + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def summarize(rows):
    groups = []
    for prompt in PROMPTS:
        for endpoint in ["generate", "generate-stream"]:
            selected = [r for r in rows if r["prompt_name"] == prompt and r["endpoint"] == endpoint]
            good = [r for r in selected if r["success"]]
            group = {"prompt_name": prompt, "endpoint": endpoint, "attempted": len(selected),
                     "successful": len(good), "failed": len(selected) - len(good)}
            for metric in METRICS:
                values = [r[metric] for r in good if r.get(metric) is not None]
                group[metric] = {"n": len(values), "mean": statistics.mean(values),
                                 "p50": percentile(values, .5), "p95": percentile(values, .95)} if values else None
            group["output_tokens"] = {"min": min(r["output_tokens"] for r in good),
                                      "max": max(r["output_tokens"] for r in good)} if good else None
            groups.append(group)
    return groups


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Must be a positive integer")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="benchmark_results/results.csv")
    parser.add_argument("--runs", type=positive, default=30)
    parser.add_argument("--warmup", type=positive, default=2)
    parser.add_argument("--max-new-tokens", type=positive, default=32)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--timeout", type=positive, default=120)
    parser.add_argument("--hardware-label", required=True, help="Actual SERVER hardware, not the client machine")
    args = parser.parse_args()
    if not args.hardware_label.strip():
        parser.error("--hardware-label must describe the actual server hardware")
    if args.max_new_tokens > 256:
        parser.error("--max-new-tokens must be at most 256")
    url, output = args.url.rstrip("/"), Path(args.output)
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        parser.error("--url must be an HTTP(S) origin without credentials, a path or query")
    output.parent.mkdir(parents=True, exist_ok=True)
    if any(p.exists() for p in [output, output.with_suffix(".manifest.json"), output.with_suffix(".summary.json")]):
        parser.error("Output already exists; choose a fresh path to preserve prior runs")
    cases = [(name, endpoint) for name in PROMPTS for endpoint in ["generate", "generate-stream"]]
    request_config = {"max_new_tokens": args.max_new_tokens, "temperature": 0.0}
    started = datetime.now(timezone.utc).isoformat()
    rows, warmups = [], []
    def run(session, prompt, endpoint):
        return measure(session, url, endpoint, {"prompt": PROMPTS[prompt], **request_config}, args.timeout)
    with requests.Session() as session:
        for prompt, endpoint in cases:
            for _ in range(args.warmup):
                warmups.append({"prompt_name": prompt, "endpoint": endpoint, **run(session, prompt, endpoint)})
        response = session.get(f"{url}/benchmark-info", timeout=args.timeout)
        response.raise_for_status()
        server = response.json()
        schedule = [(name, endpoint, repetition) for name, endpoint in cases for repetition in range(args.runs)]
        random.Random(args.seed).shuffle(schedule)
        for sequence, (prompt, endpoint, repetition) in enumerate(schedule):
            row = {"sequence": sequence, "prompt_name": prompt, "endpoint": endpoint, "request_id": repetition}
            try:
                row.update(run(session, prompt, endpoint), success=True, error="")
            except (requests.RequestException, ValueError, KeyError) as error:
                row.update(success=False, error=type(error).__name__ + ": " + str(error).split("\n")[0][:200])
            rows.append(row)
            print(f"{sequence + 1}/{len(schedule)} {prompt}/{endpoint}: {'ok' if row['success'] else 'FAILED'}", flush=True)
    with output.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=sorted({k for row in rows for k in row}))
        writer.writeheader(); writer.writerows(rows)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip())
    manifest = {
        "schema_version": 1, "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
        "measurement_scope": "Serial warmed Python HTTP serving. Server generation excludes tokenization/model loading; client wall and first non-empty SSE text include transport and buffering.",
        "hardware_label": args.hardware_label, "server": server,
        "client": {"python": platform.python_version(), "platform": platform.platform(), "requests": requests.__version__},
        "configuration": vars(args), "request": request_config, "prompts": PROMPTS,
        "order_seed": args.seed, "excluded_warmups": warmups,
        "git_revision": revision, "working_tree_dirty": dirty,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "csv_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "attempted": len(rows), "failed": sum(not r["success"] for r in rows),
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    output.with_suffix(".summary.json").write_text(json.dumps(summarize(rows), indent=2) + "\n")
    print(f"Wrote {len(rows)} rows plus manifest and summary to {output}")
    if manifest["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
