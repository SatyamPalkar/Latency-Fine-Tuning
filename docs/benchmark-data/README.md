# Apple M3 Pro CPU reference run

This is a measured, warmed Python-server baseline. It is not the browser demo.

- Hardware: Apple M3 Pro; CPU inference; 1 PyTorch thread; macOS arm64; shared interactive workstation
- 180 measured requests; 0 failures; 12 excluded warmups.
- Source commit: `d4670b30b0f0c50ec3cca86849b09a81a9036671`.
- distilgpt2 revision: `2290a62682d06624634c1f46a6ad5be0f47f38aa`.
- Python 3.13.5, PyTorch 2.9.0, Transformers 4.57.1; 1 CPU thread.
- Greedy decoding; all six cases produced 32 output tokens per measured request.
- Workstation was shared; power mode and thermal state were not controlled.

| Prompt | Endpoint | n | TTFT p50 ms | TTFT p95 ms | Generation p50 ms | HTTP wall p50 ms | First text p50 ms | Mean tokens/s |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| short | generate | 30 | 7.19 | 7.42 | 170.78 | 172.38 | — | 187.03 |
| short | generate-stream | 30 | 7.35 | 7.80 | 176.21 | 177.86 | 8.82 | 180.87 |
| medium | generate | 30 | 12.12 | 12.68 | 177.75 | 179.41 | — | 179.43 |
| medium | generate-stream | 30 | 12.30 | 13.45 | 186.32 | 187.98 | 13.87 | 172.26 |
| long | generate | 30 | 17.48 | 17.85 | 184.64 | 186.42 | — | 172.41 |
| long | generate-stream | 30 | 17.60 | 17.90 | 193.48 | 195.30 | 19.34 | 164.83 |

The longer prompts have higher observed TTFT in this run. Streaming and JSON
responses use different delivery paths; these results do not establish an
optimization speedup. p95 with 30 observations is exploratory, not a guarantee.

The manifest's dirty flag includes the newly generated untracked benchmark
artifacts. The runner hash and source commit identify the measured implementation;
the raw CSV checksum is verified before report rendering. Timestamps, prompts,
all warmups and actual output-token ranges are retained in the adjacent files.

Reproduce with [BENCHMARKS.md](../../BENCHMARKS.md). Raw requests, manifest and
summary are adjacent to this README. The former historical plots remain separate.
