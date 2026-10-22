"""Verify a benchmark's hashes and render an auditable static reference report."""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path


def render(csv_path, output):
    csv_path, output = Path(csv_path), Path(output)
    manifest = json.loads(csv_path.with_suffix(".manifest.json").read_text())
    summary = json.loads(csv_path.with_suffix(".summary.json").read_text())
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != manifest["csv_sha256"]:
        raise ValueError("CSV hash does not match its manifest")
    with csv_path.open() as file:
        rows = list(csv.DictReader(file))
    failed = sum(row["success"] != "True" for row in rows)
    if len(rows) != manifest["attempted"] or failed != manifest["failed"]:
        raise ValueError("Request counts do not match the manifest")
    if sum(group["attempted"] for group in summary) != len(rows):
        raise ValueError("Summary request counts do not match CSV")
    def value(group, key, statistic="p50"):
        return f'{group[key][statistic]:,.2f}' if group.get(key) else "—"
    table = []
    markdown = []
    for group in summary:
        cells = [group["prompt_name"], group["endpoint"], str(group["successful"]),
                 value(group, "ttft_ms"), value(group, "ttft_ms", "p95"),
                 value(group, "total_latency_ms"), value(group, "wall_latency_ms"),
                 value(group, "client_first_text_ms"), value(group, "tokens_per_second", "mean")]
        table.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")
        markdown.append("| " + " | ".join(cells) + " |")
    server = manifest["server"]
    detail = html.escape(json.dumps({"hardware": manifest["hardware_label"], "server": server,
                                     "request": manifest["request"], "source_commit": manifest["git_revision"]}, indent=2))
    stem = csv_path.stem
    downloads = " · ".join(f'<a href="./benchmark-data/{html.escape(stem + suffix)}">{label}</a>' for suffix, label in
                             [(".csv", "Raw requests"), (".manifest.json", "Provenance manifest"), (".summary.json", "Summary JSON")])
    report = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Latency Lab | Reproducible CPU Benchmark</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f3ec;color:#25372c;font:17px/1.65 system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:40px 22px}}a{{color:#246b52}}h1{{font-size:clamp(30px,5vw,52px);line-height:1.1}}.eyebrow{{letter-spacing:2px;font-size:12px}}.cards{{display:flex;gap:20px;flex-wrap:wrap;margin:30px 0}}.cards div{{background:white;border:1px solid #d8ded4;padding:18px 25px;border-radius:12px}}.cards strong{{display:block;font-size:30px}}.table{{overflow:auto}}table{{border-collapse:collapse;min-width:1000px;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #cdd7ce}}th{{background:#e4eade}}pre{{padding:20px;background:#e8ece2;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}.note{{padding:20px;border-left:3px solid #3a785e;background:#edf0e7}}li{{margin-bottom:10px}}
</style></head><body><main><a href="./">← Live inference</a><p class="eyebrow">MEASURED PYTHON SERVER BASELINE</p><h1>Reproducible CPU benchmarks.</h1>
<p>Three frozen prompts. Two HTTP endpoints. {manifest['configuration']['runs']} measured repetitions per case. This is a local Python-server experiment, separate from the browser demo.</p>
<div class="cards"><div><strong>{len(rows)}</strong>measured requests</div><div><strong>{len(manifest['excluded_warmups'])}</strong>excluded warmups</div><div><strong>{failed}</strong>failed requests</div></div>
<p>{html.escape(manifest['hardware_label'])}<br>Completed {html.escape(manifest['completed_utc'])}</p>
<div class="table"><table><thead><tr><th>Prompt</th><th>Endpoint</th><th>n</th><th>Server TTFT p50 ms</th><th>TTFT p95 ms</th><th>Generation p50 ms</th><th>HTTP wall p50 ms</th><th>First text p50 ms</th><th>Mean tokens/s</th></tr></thead><tbody>{''.join(table)}</tbody></table></div>
<p>{downloads}</p><div class="note">A reproducible baseline is not a speedup claim. The serial run measures warmed inference on one workstation; it does not establish production tail latency or multi-user capacity.</div>
<h2>What the timings mean</h2><ul><li>Server TTFT observes the first generated token, before text buffering. Generation excludes model loading and prompt tokenization.</li><li>Client first text includes HTTP transport and word buffering. It is not token-level TTFT. Loopback does not represent Internet latency.</li><li>Greedy decoding, 32 requested output tokens, one CPU thread and a pinned model revision make the setup explicit. Token ranges and any failures remain in the artifacts.</li><li>p95 uses linear interpolation over successful observations. Thirty repetitions per case are exploratory; independent repetitions and controlled power/thermal conditions are needed for stronger claims.</li><li>The workstation was shared and power/thermal state was not controlled. No GPU, cold-start, concurrent-load or browser benchmarks are included here.</li></ul>
<h2>Environment and settings</h2><pre>{detail}</pre><p><a href="https://github.com/SatyamPalkar/Latency-Fine-Tuning/blob/latency-deployment/BENCHMARKS.md">Reproduction instructions and timing contract ↗</a></p>
<p><a href="./historical-benchmarks.html">Older historical charts</a> · <a href="./">Return to browser demo</a></p></main></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    readme = f'''# Apple M3 Pro CPU reference run

This is a measured, warmed Python-server baseline. It is not the browser demo.

- Hardware: {manifest['hardware_label']}
- {len(rows)} measured requests; {failed} failures; {len(manifest['excluded_warmups'])} excluded warmups.
- Source commit: `{manifest['git_revision']}`.
- distilgpt2 revision: `{server['model_revision']}`.
- Python {server['python']}, PyTorch {server['torch']}, Transformers {server['transformers']}; {server['torch_threads']} CPU thread.
- Greedy decoding; all six cases produced 32 output tokens per measured request.
- Workstation was shared; power mode and thermal state were not controlled.

| Prompt | Endpoint | n | TTFT p50 ms | TTFT p95 ms | Generation p50 ms | HTTP wall p50 ms | First text p50 ms | Mean tokens/s |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(markdown)}

The longer prompts have higher observed TTFT in this run. Streaming and JSON
responses use different delivery paths; these results do not establish an
optimization speedup. p95 with 30 observations is exploratory, not a guarantee.

The manifest's dirty flag includes the newly generated untracked benchmark
artifacts. The runner hash and source commit identify the measured implementation;
the raw CSV checksum is verified before report rendering. Timestamps, prompts,
all warmups and actual output-token ranges are retained in the adjacent files.

Reproduce with [BENCHMARKS.md](../../BENCHMARKS.md). Raw requests, manifest and
summary are adjacent to this README. The former historical plots remain separate.
'''
    csv_path.parent.joinpath("README.md").write_text(readme)
    print(f"Verified {len(rows)} request rows; rendered {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="benchmarks/reference/apple-m3-pro-cpu.csv")
    parser.add_argument("--output", default="dashboard/reference.html")
    args = parser.parse_args()
    render(args.csv, args.output)
