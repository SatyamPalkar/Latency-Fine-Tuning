# LLM TTFT Optimization Platform

A Dockerized FastAPI service for measuring and improving **Time To First Token (TTFT)** in local LLM inference.

This project is intentionally scoped as a two-week, hiring-manager-friendly MVP: it focuses on inference APIs, streaming, latency instrumentation, reproducible benchmarks, tests, Docker, and clear benchmark charts.

## Business Problem

LLM applications can feel slow even when total generation time is acceptable. For chat and assistant products, the first visible token strongly affects perceived responsiveness. This project benchmarks TTFT, total latency, and tokens/sec across prompt lengths and response modes so an ML engineer can reason about latency-quality trade-offs instead of guessing.

## What This Project Demonstrates

- FastAPI model serving
- Streaming and non-streaming generation endpoints
- TTFT, total latency, and tokens/sec measurement
- Reproducible benchmark scripts
- Dockerized local deployment
- pytest validation for API contracts and metrics
- README-ready latency charts

## Architecture

```text
Client / Benchmark Script
        |
        v
FastAPI Service
        |
        v
Hugging Face Causal LM
        |
        v
Latency Metrics
TTFT | total latency | tokens/sec | token counts
        |
        v
Benchmark CSV
        |
        v
Charts + Analysis
```

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
make run
```

Then open:

```text
http://localhost:8000/docs
```

## Docker

```bash
docker compose up --build
```

## API Examples

Health check:

```bash
curl http://localhost:8000/health
```

Generate:

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain TTFT in one paragraph.","max_new_tokens":60}'
```

Stream:

```bash
curl -N -X POST http://localhost:8000/generate-stream \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain why LLM streaming improves user experience.","max_new_tokens":60}'
```

## Benchmarking

Start the API, then run:

```bash
make benchmark
make plots
make dashboard
```

Outputs:

```text
benchmark_results/results.csv
plots/ttft_by_prompt_length.png
plots/total_latency_by_prompt_length.png
plots/tokens_per_second.png
dashboard/index.html
```

Open the benchmark dashboard in your browser:

```text
dashboard/index.html
```

## Testing

```bash
make test
make lint
```

## Initial Scope

Included:

- `/health`
- `/generate`
- `/generate-stream`
- TTFT metrics
- CSV benchmarks
- latency plots
- Docker setup
- tests

Deferred intentionally:

- LoRA fine-tuning
- vLLM
- cloud deployment
- MLflow
- Prometheus/Grafana

These are good phase-two improvements after the core latency story is working.
