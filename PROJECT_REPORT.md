# LLM TTFT Optimization Platform - Project Report

## 1. Project Summary

This project is a production-style LLM inference benchmarking system focused on measuring **Time To First Token (TTFT)**, total generation latency, token throughput, and API behavior for a locally served language model.

The current version is an MVP designed for a two-week portfolio project. It includes a FastAPI inference service, streaming and non-streaming endpoints, latency instrumentation, benchmark scripts, chart generation scripts, Docker configuration, automated tests, linting, and a README.

The main goal is not to build the largest LLM application. The goal is to demonstrate that the developer understands how LLM systems are served, measured, tested, containerized, and analyzed from an ML engineering perspective.

## 2. Business Problem

LLM-powered products often feel slow to users because the first response takes too long to appear. Even when total generation latency is acceptable, a high TTFT can make chatbots, coding assistants, support assistants, and AI copilots feel unresponsive.

This project simulates the work an ML engineer might do inside a company that already has an LLM assistant but needs to understand and reduce user-perceived latency.

The system helps answer questions such as:

- How long does the model take to return the first visible token?
- How does prompt length affect latency?
- How do streaming and non-streaming responses compare?
- What is the token generation throughput?
- What metrics should be tracked before optimizing inference?

## 3. Why This Project Matters

This project demonstrates practical ML engineering skills beyond model training. It shows experience with model serving, API design, reproducibility, benchmarking, latency analysis, and testing.

For a fresh graduate, this is valuable because many ML portfolios only show notebooks. This project instead shows a working service that can be run, tested, benchmarked, and improved.

The strongest resume signal is:

> Built a Dockerized FastAPI LLM inference service with streaming responses and TTFT benchmarking to analyze LLM latency across prompt lengths and inference modes.

## 4. Current Scope

The current project includes:

- FastAPI backend
- Hugging Face model loading
- Non-streaming generation endpoint
- Streaming generation endpoint
- TTFT metric collection for streaming responses
- Total latency measurement
- Token counting
- Tokens-per-second calculation
- Benchmark script
- Plot generation script
- HTML benchmark dashboard generator
- Dockerfile
- docker-compose setup
- pytest tests
- Ruff linting
- README documentation

The current project intentionally does not include:

- LoRA fine-tuning
- vLLM
- MLflow
- Prometheus/Grafana monitoring
- Cloud deployment
- Kubernetes
- Model quantization
- Authentication
- Production-grade rate limiting

These are left as future improvements so the project remains realistic and explainable.

## 5. Repository Structure

```text
.
├── api/
│   ├── __init__.py
│   ├── main.py
│   └── schemas.py
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── generation.py
│   ├── metrics.py
│   └── model_loader.py
├── scripts/
│   ├── run_benchmark.py
│   ├── make_plots.py
│   └── make_dashboard.py
├── dashboard/
│   └── index.html
├── tests/
│   ├── test_api.py
│   ├── test_metrics.py
│   └── test_schemas.py
├── benchmark_results/
├── plots/
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── requirements.txt
├── README.md
└── PROJECT_REPORT.md
```

## 6. File-by-File Explanation

### `api/main.py`

This file defines the FastAPI application.

It exposes three endpoints:

- `GET /health`
- `POST /generate`
- `POST /generate-stream`

The `/health` endpoint checks whether the API is alive.

The `/generate` endpoint performs standard non-streaming generation. It waits for the full model output before returning a response.

The `/generate-stream` endpoint streams generated text chunks back to the client and reports TTFT at the end of the stream.

### `api/schemas.py`

This file defines Pydantic request and response schemas.

It validates:

- prompt length
- max generated tokens
- temperature range

This prevents invalid API inputs from reaching the model layer.

### `src/config.py`

This file stores project configuration.

Current environment variables:

- `MODEL_NAME`
- `MAX_NEW_TOKENS`
- `DEVICE`

The default model is currently:

```text
distilgpt2
```

### `src/model_loader.py`

This file loads the Hugging Face tokenizer and model.

It automatically selects the best available device:

- CUDA if available
- Apple MPS if available
- CPU otherwise

On the current machine, the model ran on:

```text
mps
```

### `src/generation.py`

This file contains the core inference logic.

It defines `LLMGenerator`, which supports:

- regular generation
- streaming generation
- token counting
- latency calculation
- Server-Sent Events formatting

This is the most important file in the project.

### `src/metrics.py`

This file defines reusable latency metric helpers.

It includes:

- `LatencyMetrics`
- `tokens_per_second`
- percentile calculation
- latency summary helpers

### `scripts/run_benchmark.py`

This script sends repeated requests to the running API.

It benchmarks:

- short prompts
- medium prompts
- long prompts
- `/generate`
- `/generate-stream`

It writes results to:

```text
benchmark_results/results.csv
```

### `scripts/make_plots.py`

This script reads benchmark results and generates charts.

Expected outputs:

```text
plots/ttft_by_prompt_length.png
plots/total_latency_by_prompt_length.png
plots/tokens_per_second.png
```

### `scripts/make_dashboard.py`

This script reads benchmark results and generates a self-contained HTML dashboard.

Expected output:

```text
dashboard/index.html
```

The dashboard includes:

- total request count
- p95 TTFT
- mean total latency
- mean tokens per second
- bar charts by prompt length and endpoint
- grouped summary table

### `tests/`

The tests validate:

- health endpoint behavior
- request validation
- API response structure
- latency metric calculations
- percentile calculations

The tests use a fake generator so they do not need to download or run a real LLM.

### `Dockerfile`

Defines how to package the service as a Docker image.

### `docker-compose.yml`

Defines how to run the service locally with Docker Compose.

### `Makefile`

Provides simple commands:

```bash
make install
make run
make test
make lint
make benchmark
make plots
make docker-up
make docker-down
```

## 7. Current API Design

### Health Endpoint

```http
GET /health
```

Example response:

```json
{
  "status": "ok",
  "model_loaded": true
}
```

### Non-Streaming Generation

```http
POST /generate
```

Example request:

```json
{
  "prompt": "Explain TTFT in one sentence.",
  "max_new_tokens": 20,
  "temperature": 0.7
}
```

Example response:

```json
{
  "text": "...",
  "model_name": "distilgpt2",
  "device": "mps",
  "input_tokens": 8,
  "output_tokens": 20,
  "ttft_ms": null,
  "total_latency_ms": 6804.237375,
  "tokens_per_second": 2.9393448373044158
}
```

### Streaming Generation

```http
POST /generate-stream
```

The streaming endpoint uses Server-Sent Events.

It emits token chunks as they are produced and sends final metrics after generation is complete.

## 8. Metrics Explained

### TTFT

TTFT means **Time To First Token**.

It measures how long the user waits before seeing the first generated token.

This is important because users often perceive an application as faster if the first token appears quickly, even when the full response takes longer.

### Total Latency

Total latency measures the full time from request start to completed response.

This matters for workflows where the final complete answer is needed before the user can continue.

### Tokens Per Second

Tokens per second measures generation throughput.

It helps compare model speed across devices, model sizes, and serving configurations.

### Input Tokens

Input tokens measure the prompt size.

Prompt length often affects prefill time and can increase TTFT.

### Output Tokens

Output tokens measure how many tokens the model generated.

Longer outputs naturally increase total latency.

## 9. Current Verification Results

The project has been verified locally.

Tests:

```text
9 passed
```

Lint:

```text
All checks passed
```

First generation test:

```text
model_name: distilgpt2
device: mps
input_tokens: 8
output_tokens: 20
total_latency_ms: 6804.237375
tokens_per_second: 2.9393448373044158
```

## 10. Main Technical Decisions

### Why FastAPI?

FastAPI is lightweight, common in ML serving, and provides automatic API docs. It also integrates well with Pydantic validation.

### Why Hugging Face Transformers?

Hugging Face provides standard model and tokenizer loading for open-source language models.

### Why `distilgpt2`?

`distilgpt2` is small enough to run locally on a laptop. It is not chosen for response quality. It is chosen because the project focuses on inference infrastructure and latency measurement.

### Why Docker?

Docker improves reproducibility. A recruiter or interviewer can see that the project is designed to run outside a notebook.

### Why pytest?

Automated tests show that the API and metrics logic are validated. This is important for engineering credibility.

### Why benchmark scripts?

Benchmark scripts turn the project from a demo into an engineering analysis tool.

## 11. Current Limitations

The current MVP has several limitations:

- The default model is small and low-quality.
- TTFT is only measured on the streaming endpoint.
- Benchmarking is local and single-machine only.
- There is no model registry.
- There is no experiment tracking.
- There is no production observability stack.
- There is no GPU deployment configuration.
- There is no authentication or rate limiting.
- The benchmark script uses a small number of prompts.
- The benchmark results are not yet analyzed in depth.

These limitations are acceptable for the first version, but they are also the best opportunities for improvement.

## 12. What You Can Improve Yourself

The project should not stay as a GPT-generated scaffold. To make it genuinely yours, you should extend it in measurable ways.

Recommended improvements:

1. Add more benchmark prompts

   Create a larger benchmark set with 20-50 prompts across short, medium, and long categories.

2. Improve the benchmark summary

   Add a script that computes p50, p95, and p99 latency by endpoint and prompt length.

3. Add benchmark result tables to the README

   Run the benchmark and paste real numbers into the README.

4. Generate and include plots

   Add the generated charts to the README so visitors can immediately see the analysis.

5. Add streaming TTFT comparison

   Compare TTFT across prompt sizes and explain why prompt length affects first-token latency.

6. Add a better model option

   Try a stronger small model such as:

   ```text
   TinyLlama/TinyLlama-1.1B-Chat-v1.0
   ```

   Compare it against `distilgpt2`.

7. Add model configuration experiments

   Compare:

   - `max_new_tokens=20`
   - `max_new_tokens=50`
   - `max_new_tokens=100`
   - temperature 0
   - temperature 0.7

8. Add a benchmark report

   Create:

   ```text
   docs/benchmark_report.md
   ```

   Include methodology, results, interpretation, and limitations.

9. Add GitHub Actions

   Add CI that runs:

   - Ruff
   - pytest

10. Add Prometheus metrics

    Expose request counts and latency metrics from the API.

## 13. Suggested Next Milestone

The best next milestone is:

> Run the benchmark, generate plots, and write a real benchmark analysis.

This is where the project becomes yours.

Recommended sequence:

```bash
source .venv/bin/activate
make run
```

In another terminal:

```bash
make benchmark
make plots
make dashboard
```

Then inspect:

```text
benchmark_results/results.csv
plots/
dashboard/index.html
```

After that, update the README with:

- benchmark table
- chart images
- what the results mean
- what you would optimize next

## 14. Resume Bullets

Current honest resume bullet:

> Built a Dockerized FastAPI LLM inference service with streaming responses and TTFT benchmarking, measuring total latency, token throughput, and generation metrics for a locally served Hugging Face model.

Stronger version after you run benchmarks and add charts:

> Developed a reproducible LLM latency benchmarking platform using FastAPI, Hugging Face Transformers, Docker, and pytest, analyzing TTFT, p50/p95 latency, and tokens/sec across prompt lengths and streaming modes.

Even stronger version after adding your own analysis:

> Extended a local LLM inference service with benchmark automation and latency visualizations, identifying how prompt length and streaming behavior affect TTFT, total generation time, and token throughput.

## 15. Interview Talking Points

You should be able to explain:

- What TTFT means
- Why TTFT matters
- Difference between TTFT and total latency
- Why streaming improves perceived latency
- Why prompt length affects generation latency
- Why tests use a fake generator
- Why `distilgpt2` was chosen for the MVP
- How Docker helps reproducibility
- What would change if this served a larger model
- What would break at higher traffic

## 16. Interview Questions and Sample Answers

### Question 1: Why did you build this project?

Sample answer:

I wanted to build an ML engineering project focused on inference, not just training. TTFT is an important metric for LLM applications because users care about when the first response appears. This project gave me practice with FastAPI serving, streaming responses, latency measurement, Docker, testing, and benchmarking.

### Question 2: Why is TTFT different from total latency?

Sample answer:

TTFT measures the time until the first generated token is available. Total latency measures the time until the entire response is complete. In interactive applications, TTFT often affects perceived speed more than total latency because users can start reading while the rest of the answer streams.

### Question 3: Why did you use a small model?

Sample answer:

The project is designed to run locally and cheaply. I used a small model for reproducibility and focused on the serving and measurement pipeline. The same structure could be used with a larger model on a GPU server.

### Question 4: What would you improve next?

Sample answer:

I would add benchmark aggregation for p50, p95, and p99 latency, run a larger prompt set, compare multiple models, and add Prometheus metrics. After that I would try vLLM to compare throughput and batching behavior.

### Question 5: What breaks at 100x traffic?

Sample answer:

The current service loads one model instance and handles requests in a simple local setup. At much higher traffic, queueing delays, memory limits, and lack of batching would become issues. I would need a dedicated inference server such as vLLM, request batching, autoscaling, GPU monitoring, and backpressure.

## 17. Final Assessment

Current project rating for a fresh graduate:

```text
7/10 as a scaffold
8/10 after real benchmark results, plots, and analysis are added
8.5/10 after CI and richer benchmark comparison are added
```

The scaffold is useful, but the project becomes impressive only when real results and your own analysis are added.

The most important next step is to run the benchmark, generate charts, and explain the results in your own words.
