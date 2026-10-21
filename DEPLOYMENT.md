# Latency Lab deployment

The application serves the frontend, inference API, streaming responses, Plotly bundle, and benchmark dashboard from one Python service. It does not need a separate Node build or browser API key.

## Current verification

Verified locally on 22 October 2026:

- 24 automated tests passed, including readiness state, model-load recovery, concurrency rejection, context limits, and generation-thread cancellation.
- Real `distilgpt2` inference completed on CPU, using a cached safetensors model.
- Chrome completed a real streamed request and displayed valid token counts and measured timing values.
- Layouts were checked at widths of 320, 390, 768, and 1440 pixels, without horizontal overflow or uncaught JavaScript errors.
- A real HTTP streaming disconnect cancelled generation, and a following request succeeded.
- Runtime dependency declarations in `requirements.txt` and `pyproject.toml` agree.

The local environment uses Python 3.13 and reuses host-installed PyTorch/Transformers through a workspace virtual environment; project-specific API dependencies are installed in that environment. The Docker target uses Python 3.11 and Linux CPU PyTorch. Docker is not installed on this machine, so the image build, Linux resource use, and the actual cloud deployment still need verification. The local running process used approximately 604 MiB RSS after short inference requests; this is not a Linux hosting measurement or a peak-memory guarantee.

## Run locally

For a fresh environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/serve.py
```

Open http://127.0.0.1:8000. The preview started during development uses port 8008 instead. `PORT` and `HOST` environment variables override the defaults. `scripts/serve.py` also reads a local `.env` file without overriding variables already supplied by the host.

The default `distilgpt2` model is a text-completion model, not an instruction-tuned chat assistant. Start with a sentence fragment. The initial model download requires network access unless its files are cached.

## Service checks

- `/health`: process liveness plus actual model-loading state; does not claim an unloaded model is ready.
- `/ready`: HTTP 200 only after model initialization succeeds; otherwise HTTP 503.
- `POST /generate`: JSON output and generation metrics.
- `POST /generate-stream`: SSE token events followed by final metrics.
- `/benchmarks`: the checked-in historical benchmark dashboard. It is separate from the measurements of live requests.

One generation runs at a time. Overlapping requests receive HTTP 429 with `Retry-After: 2`. Requests with blank prompts, excessive output limits, or a prompt/output combination beyond the model context receive HTTP 422. Model loading and synchronous generation failures return HTTP 503 without exposing internal exception details.

`MAX_NEW_TOKENS` is a server-enforced ceiling, from 1 to 256. `GENERATION_TIMEOUT_SECONDS` bounds Hugging Face generation time between 1 and 120 seconds; it is evaluated during decoding and is not a process-level kill timer. Closing an SSE response requests cancellation of its generation thread before releasing the inference slot.

## Container deployment

```sh
docker build -t latency-lab .
docker run --rm -p 8000:8000 latency-lab
```

The Dockerfile installs Linux CPU PyTorch, includes the default model during the build, and runs as a non-root user. Only runtime source and the frontend/dashboard are copied into the final application directory. Development environments, Git metadata, local environment files, and experiment outputs are excluded.

The default model is selected with build argument `MODEL_NAME`. If you change the model, rebuild with the matching argument and verify its context window, memory requirements, license, and inference behavior. The image cache remains writable by the application user. Do not scale this template to several worker processes without accounting for one model copy per process.

## Render deployment

`render.yaml` describes one Docker web service with:

- one instance and one Uvicorn worker;
- CPU inference, startup model preloading, and a 45-second generation budget;
- the platform port set to 10000 and binding on `0.0.0.0`;
- `/ready` as the deployment health check;
- automatic deployments disabled;
- an explicit `1c-2g` compute plan, rather than the default 512 MB plan.

This is a paid compute configuration. Review the current price and account/workspace selection before provisioning it. No Render service has been created by adding this file. The 2 GB setting is a starting configuration that still requires Linux memory verification.

To finish:

1. Make the prepared Git branch available to the hosting provider.
2. Connect the intended Render account and GitHub repository.
3. Review the service name, compute plan and price, branch, and environment variables.
4. Run the first cloud build. Confirm `/ready`, a real streamed request, browser assets, and the benchmark page at the returned HTTPS URL.
5. Add that verified URL to the portfolio; do not use a guessed hostname.

References: [Render Docker deployments](https://render.com/docs/docker), [Blueprint fields](https://render.com/docs/blueprint-spec), and [port binding](https://render.com/docs/web-services#port-binding).

## Optional development tools

```sh
pip install -r requirements-dev.txt
python -m pytest -q
```

Plotting and benchmark-generation dependencies are separate:

```sh
pip install -r requirements-benchmark.txt
make benchmark
make plots
make dashboard
```

Do not describe the historic sample charts as measurements from the new cloud host. Run fresh benchmarks for that host and keep their hardware and timing boundaries documented.
