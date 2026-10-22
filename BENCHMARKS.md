# Reproducing Latency Lab benchmarks

This protocol measures the Python model server. The GitHub Pages demo executes
ONNX/WASM on a visitor's device; its timings are a separate experiment and must
not be pooled with Python measurements.

## Controlled serving process

Use the project environment after installing `requirements.txt`. The committed
reference model revision is the immutable distilgpt2 snapshot below. CPU thread
counts are explicit, and one server worker handles one active generation.

```sh
MODEL_NAME=distilgpt2 \
MODEL_REVISION=2290a62682d06624634c1f46a6ad5be0f47f38aa \
DEVICE=cpu PRELOAD_MODEL=true OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
TOKENIZERS_PARALLELISM=false PORT=8000 python scripts/serve.py
```

Do not benchmark a shared process while browsing its inference UI. Confirm
`/ready` returns 200 before the run. Model files require an initial download
unless cached; network/model loading are excluded by the warmup protocol.

## Run the experiment

The runner needs `requests`, included in `requirements-benchmark.txt`. Heavy
plotting libraries are needed only for the optional historical chart generator.

```sh
python scripts/run_benchmark.py \
  --url http://127.0.0.1:8000 \
  --runs 30 --warmup 2 --max-new-tokens 32 --seed 2026 \
  --hardware-label "YOUR ACTUAL SERVER CPU/GPU" \
  --output benchmark_results/my-machine.csv
```

Three frozen completion prompts × two endpoints × 30 measured repetitions gives
180 measured requests. Two warmups per case add 12 excluded requests. Greedy
decoding (`temperature=0`) avoids stochastic output-length changes; EOS and the
server time budget can still end a response before the requested token ceiling.
Output token ranges are reported. Request order is shuffled with a recorded seed
to reduce fixed endpoint-order bias. Requests remain serial: this is not a
concurrent load or capacity benchmark.

The runner refuses to overwrite an existing experiment. Failures are retained as
failed rows and counted in the summary, never turned into zero-latency successes.
A failed measured request yields a nonzero exit after saving results. A failed
warmup or missing server metadata aborts before measured requests. The client does
not retry failed requests. HTTP read timeouts are inactivity timeouts, not a total
experiment deadline.

## Artifacts and boundaries

Each run produces:

- `.csv`: raw measured rows, order, repetition, success/error, token counts and timings.
- `.manifest.json`: exact prompts/settings, excluded warmups, timestamps, server
  runtime/model revision/thread count, separately identified client environment,
  hardware label, runner-checkout commit/dirty flag, runner hash and CSV SHA-256.
  The runner's commit is not an independently attested remote-server revision.
- `.summary.json`: attempted/success/failed counts, mean/p50/p95 with sample counts,
  and output-token ranges for every prompt/endpoint pair.

`ttft_ms` is the server's first **generated token** callback, before word buffering.
`total_latency_ms` spans server generation and device synchronization, excluding
model loading and prompt tokenization. Streaming includes generation-thread launch
overhead. `tokens_per_second` divides generated tokens by that total. Special
tokens count even if not displayed.

`wall_latency_ms` spans the client HTTP call through the complete response.
`client_first_text_ms` records the first nonempty SSE text event; it includes
transport and the text streamer's word buffering. It is not token-level TTFT.
The streaming client reads one-byte chunks to avoid requests' default buffer
hiding the first text event. Local loopback measurements do not describe public
Internet latency. The first text may legitimately arrive after several tokens.

Percentiles use linear interpolation over successful observations. Thirty
repetitions per case support an exploratory local comparison, not a precise tail
latency guarantee or statistically established speedup. Repeat independent runs
on the same hardware/settings before drawing optimization conclusions. Record
power mode, competing workloads and thermal conditions where possible.

## Reference results

Reference measurements and their limitations are documented in
`benchmarks/reference/README.md`. The older `dashboard/index.html` and `plots/`
files remain clearly identified as historical samples until explicitly rebuilt;
they are not results from the new protocol.
