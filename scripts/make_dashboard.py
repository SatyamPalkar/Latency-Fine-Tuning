from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Optional

import pandas as pd

PROMPT_ORDER = ["short", "medium", "long"]
ENDPOINT_ORDER = ["generate", "generate-stream"]
COLORS = {
    "generate": "#2563eb",
    "generate-stream": "#16a34a",
}


def percentile(values: pd.Series, pct: float) -> float:
    if values.empty:
        return 0.0
    return float(values.quantile(pct / 100))


def format_number(value: object, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.1f}{suffix}"


def metric_card(label: str, value: str, note: str) -> str:
    return f"""
    <article class="metric-card">
      <span>{html.escape(label)}</span>
      <strong>{html.escape(value)}</strong>
      <small>{html.escape(note)}</small>
    </article>
    """


def grouped_summary(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["endpoint", "prompt_name"], dropna=False)
        .agg(
            requests=("request_id", "count"),
            mean_ttft_ms=("ttft_ms", "mean"),
            p50_ttft_ms=("ttft_ms", lambda values: percentile(values.dropna(), 50)),
            p95_ttft_ms=("ttft_ms", lambda values: percentile(values.dropna(), 95)),
            mean_total_latency_ms=("total_latency_ms", "mean"),
            p95_total_latency_ms=(
                "total_latency_ms",
                lambda values: percentile(values.dropna(), 95),
            ),
            mean_tokens_per_second=("tokens_per_second", "mean"),
            mean_output_tokens=("output_tokens", "mean"),
        )
        .reset_index()
    )
    grouped["prompt_rank"] = grouped["prompt_name"].apply(
        lambda name: PROMPT_ORDER.index(name) if name in PROMPT_ORDER else len(PROMPT_ORDER)
    )
    grouped["endpoint_rank"] = grouped["endpoint"].apply(
        lambda name: ENDPOINT_ORDER.index(name) if name in ENDPOINT_ORDER else len(ENDPOINT_ORDER)
    )
    return grouped.sort_values(["prompt_rank", "endpoint_rank"]).drop(
        columns=["prompt_rank", "endpoint_rank"]
    )


def bar_chart(
    summary: pd.DataFrame,
    metric: str,
    title: str,
    ylabel: str,
    include_endpoint: Optional[str] = None,
) -> str:
    chart_df = summary.copy()
    if include_endpoint:
        chart_df = chart_df[chart_df["endpoint"] == include_endpoint]
    chart_df = chart_df.dropna(subset=[metric])
    max_value = float(chart_df[metric].max()) if not chart_df.empty else 0.0
    if max_value <= 0:
        return empty_chart(title, "No data available for this metric yet.")

    rows = []
    for _, row in chart_df.iterrows():
        value = float(row[metric])
        width = max(2, int((value / max_value) * 100))
        endpoint = str(row["endpoint"])
        prompt_name = str(row["prompt_name"])
        color = COLORS.get(endpoint, "#475569")
        label = f"{html.escape(prompt_name)} {html.escape(endpoint)}"
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">
                <strong>{html.escape(prompt_name)}</strong>
                <span>{html.escape(endpoint)}</span>
              </div>
              <div class="bar-track" aria-label="{label}">
                <div class="bar-fill" style="width:{width}%;background:{color};"></div>
              </div>
              <code>{format_number(value, " ms" if metric.endswith("_ms") else "")}</code>
            </div>
            """
        )

    return f"""
    <section class="panel">
      <div class="panel-heading">
        <h2>{html.escape(title)}</h2>
        <p>{html.escape(ylabel)}</p>
      </div>
      <div class="bars">
        {''.join(rows)}
      </div>
    </section>
    """


def empty_chart(title: str, message: str) -> str:
    return f"""
    <section class="panel">
      <div class="panel-heading">
        <h2>{html.escape(title)}</h2>
      </div>
      <div class="empty">{html.escape(message)}</div>
    </section>
    """


def summary_table(summary: pd.DataFrame) -> str:
    rows = []
    for _, row in summary.iterrows():
        rows.append(
            f"""
            <tr>
              <td>{html.escape(str(row["prompt_name"]))}</td>
              <td><span class="pill">{html.escape(str(row["endpoint"]))}</span></td>
              <td>{int(row["requests"])}</td>
              <td>{format_number(row["p50_ttft_ms"], " ms")}</td>
              <td>{format_number(row["p95_ttft_ms"], " ms")}</td>
              <td>{format_number(row["mean_total_latency_ms"], " ms")}</td>
              <td>{format_number(row["p95_total_latency_ms"], " ms")}</td>
              <td>{format_number(row["mean_tokens_per_second"])}</td>
            </tr>
            """
        )

    return f"""
    <section class="panel wide">
      <div class="panel-heading">
        <h2>Benchmark Summary</h2>
        <p>Grouped by prompt length and endpoint.</p>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Prompt</th>
              <th>Endpoint</th>
              <th>Requests</th>
              <th>p50 TTFT</th>
              <th>p95 TTFT</th>
              <th>Mean Total</th>
              <th>p95 Total</th>
              <th>Mean tok/s</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </section>
    """


def render_dashboard(df: pd.DataFrame, input_path: Path) -> str:
    summary = grouped_summary(df)
    stream_df = df[df["endpoint"] == "generate-stream"].dropna(subset=["ttft_ms"])
    ttft_chart = bar_chart(
        summary,
        "p95_ttft_ms",
        "p95 TTFT by Prompt Length",
        "Lower is better. Streaming endpoint only.",
        "generate-stream",
    )
    total_latency_chart = bar_chart(
        summary,
        "p95_total_latency_ms",
        "p95 Total Latency",
        "End-to-end response latency by endpoint.",
    )
    throughput_chart = bar_chart(
        summary,
        "mean_tokens_per_second",
        "Mean Tokens Per Second",
        "Higher is better.",
    )
    output_tokens_chart = bar_chart(
        summary,
        "mean_output_tokens",
        "Mean Output Tokens",
        "Useful context when comparing total latency.",
    )

    cards = [
        metric_card("Total Requests", str(len(df)), "Rows in benchmark CSV"),
        metric_card(
            "p95 TTFT",
            format_number(percentile(stream_df["ttft_ms"], 95), " ms"),
            "Streaming endpoint only",
        ),
        metric_card(
            "Mean Total Latency",
            format_number(float(df["total_latency_ms"].mean()), " ms"),
            "Across all benchmarked requests",
        ),
        metric_card(
            "Mean Throughput",
            format_number(float(df["tokens_per_second"].mean())),
            "Generated tokens per second",
        ),
    ]

    return page_template(
        body=f"""
        <section class="hero">
          <div>
            <p class="eyebrow">LLM Inference Benchmark Dashboard</p>
            <h1>TTFT, Latency, and Throughput</h1>
            <p>
              Generated from <code>{html.escape(str(input_path))}</code>. Use this dashboard to
              compare streaming and non-streaming inference behavior across prompt lengths.
            </p>
          </div>
        </section>

        <section class="metrics">
          {''.join(cards)}
        </section>

        <main class="grid">
          {ttft_chart}
          {total_latency_chart}
          {throughput_chart}
          {output_tokens_chart}
          {summary_table(summary)}
        </main>
        """
    )


def render_empty(input_path: Path) -> str:
    return page_template(
        body=f"""
        <section class="hero">
          <div>
            <p class="eyebrow">LLM Inference Benchmark Dashboard</p>
            <h1>No Benchmark Data Yet</h1>
            <p>
              I could not find <code>{html.escape(str(input_path))}</code>. Start the API, run the
              benchmark, then regenerate this dashboard.
            </p>
          </div>
        </section>

        <section class="panel wide">
          <div class="panel-heading">
            <h2>Commands</h2>
            <p>Run these from the project root.</p>
          </div>
          <pre><code>source .venv/bin/activate
make run

# In another terminal
make benchmark
make dashboard</code></pre>
        </section>
        """
    )


def page_template(body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LLM TTFT Benchmark Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-2: #eef2f7;
      --text: #0f172a;
      --muted: #64748b;
      --line: #dbe3ef;
      --blue: #2563eb;
      --green: #16a34a;
      --shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    }}

    code, pre {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    }}

    .hero {{
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      padding: 48px 28px 34px;
    }}

    .hero > div,
    .metrics,
    .grid {{
      max-width: 1180px;
      margin: 0 auto;
    }}

    .eyebrow {{
      margin: 0 0 10px;
      color: var(--blue);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0;
    }}

    h1 {{
      margin: 0;
      font-size: clamp(32px, 5vw, 56px);
      line-height: 1;
      letter-spacing: 0;
    }}

    .hero p:last-child {{
      max-width: 780px;
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.6;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      padding: 24px 28px 4px;
    }}

    .metric-card,
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}

    .metric-card {{
      padding: 18px;
    }}

    .metric-card span,
    .metric-card small,
    .panel-heading p,
    .bar-label span {{
      color: var(--muted);
    }}

    .metric-card span {{
      display: block;
      font-size: 13px;
      font-weight: 700;
    }}

    .metric-card strong {{
      display: block;
      margin-top: 10px;
      font-size: 28px;
      line-height: 1;
    }}

    .metric-card small {{
      display: block;
      margin-top: 10px;
      line-height: 1.4;
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      padding: 20px 28px 48px;
    }}

    .panel {{
      padding: 20px;
      min-width: 0;
    }}

    .wide {{
      grid-column: 1 / -1;
    }}

    .panel-heading {{
      margin-bottom: 18px;
    }}

    h2 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }}

    .panel-heading p {{
      margin: 6px 0 0;
      line-height: 1.45;
    }}

    .bars {{
      display: grid;
      gap: 14px;
    }}

    .bar-row {{
      display: grid;
      grid-template-columns: 135px minmax(120px, 1fr) 92px;
      align-items: center;
      gap: 12px;
    }}

    .bar-label strong,
    .bar-label span {{
      display: block;
      font-size: 13px;
    }}

    .bar-track {{
      height: 13px;
      overflow: hidden;
      background: var(--surface-2);
      border-radius: 999px;
    }}

    .bar-fill {{
      height: 100%;
      border-radius: 999px;
    }}

    .bar-row code {{
      color: var(--text);
      font-size: 12px;
      text-align: right;
    }}

    .table-wrap {{
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 860px;
    }}

    th,
    td {{
      border-bottom: 1px solid var(--line);
      padding: 12px 10px;
      text-align: left;
      font-size: 14px;
      white-space: nowrap;
    }}

    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}

    .pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      background: var(--surface-2);
      padding: 4px 9px;
      font-size: 12px;
      font-weight: 700;
    }}

    .empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      color: var(--muted);
      padding: 28px;
      text-align: center;
    }}

    pre {{
      margin: 0;
      overflow-x: auto;
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 8px;
      padding: 18px;
      line-height: 1.55;
    }}

    @media (max-width: 860px) {{
      .metrics,
      .grid {{
        grid-template-columns: 1fr;
      }}

      .bar-row {{
        grid-template-columns: 1fr;
        gap: 7px;
      }}

      .bar-row code {{
        text-align: left;
      }}
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="benchmark_results/results.csv")
    parser.add_argument("--output", default="dashboard/index.html")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        output_path.write_text(render_empty(input_path), encoding="utf-8")
        print(f"No benchmark CSV found. Wrote empty dashboard to {output_path}")
        return

    df = pd.read_csv(input_path)
    output_path.write_text(render_dashboard(df, input_path), encoding="utf-8")
    print(f"Wrote benchmark dashboard to {output_path}")


if __name__ == "__main__":
    main()
