from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

PROMPT_ORDER = ["short", "medium", "long"]
ENDPOINT_ORDER = ["generate", "generate-stream"]
PALETTE = {
    "generate": "#2f6fed",
    "generate-stream": "#1fa971",
}


def percentile(values: pd.Series, pct: float) -> float:
    if values.empty:
        return 0.0
    return float(values.quantile(pct / 100))


def format_number(value: object, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.1f}{suffix}"


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    numeric_columns = [
        "input_tokens",
        "output_tokens",
        "tokens_per_second",
        "total_latency_ms",
        "ttft_ms",
        "wall_latency_ms",
    ]
    for column in numeric_columns:
        if column in df:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["prompt_name"] = pd.Categorical(
        df["prompt_name"],
        categories=PROMPT_ORDER,
        ordered=True,
    )
    df["endpoint"] = pd.Categorical(
        df["endpoint"],
        categories=ENDPOINT_ORDER,
        ordered=True,
    )
    return df.sort_values(["prompt_name", "endpoint", "request_id"])


def grouped_summary(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby(["endpoint", "prompt_name"], observed=False, dropna=False)
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
    return grouped[grouped["requests"] > 0].sort_values(["prompt_name", "endpoint"])


def apply_chart_style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 24, "r": 18, "t": 16, "b": 32},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, -apple-system, Segoe UI, sans-serif", "size": 13},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        hoverlabel={
            "bgcolor": "#ffffff",
            "bordercolor": "#d8e0eb",
            "font_size": 13,
            "font_family": "Inter, system-ui, sans-serif",
        },
        xaxis={"showgrid": False, "zeroline": False},
        yaxis={"gridcolor": "#e8edf5", "zeroline": False},
    )
    return fig


def grouped_bar(
    summary: pd.DataFrame,
    metric: str,
    y_title: str,
    endpoint_filter: Optional[str] = None,
) -> go.Figure:
    chart_df = summary.dropna(subset=[metric])
    if endpoint_filter is not None:
        chart_df = chart_df[chart_df["endpoint"].astype(str) == endpoint_filter]

    fig = go.Figure()
    endpoints = [endpoint_filter] if endpoint_filter else ENDPOINT_ORDER
    for endpoint in endpoints:
        endpoint_df = chart_df[chart_df["endpoint"].astype(str) == endpoint]
        if endpoint_df.empty:
            continue
        fig.add_trace(
            go.Bar(
                name=endpoint,
                x=endpoint_df["prompt_name"].astype(str),
                y=endpoint_df[metric],
                marker_color=PALETTE.get(endpoint, "#62748e"),
                customdata=endpoint_df[["requests"]],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    f"{html.escape(y_title)}: %{{y:,.1f}}<br>"
                    "requests: %{customdata[0]}<extra></extra>"
                ),
            )
        )
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text=y_title)
    return apply_chart_style(fig)


def latency_scatter(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for endpoint in ENDPOINT_ORDER:
        endpoint_df = df[df["endpoint"].astype(str) == endpoint]
        if endpoint_df.empty:
            continue
        fig.add_trace(
            go.Scatter(
                name=endpoint,
                x=endpoint_df["input_tokens"],
                y=endpoint_df["total_latency_ms"],
                mode="markers",
                marker={
                    "size": endpoint_df["output_tokens"].fillna(1).clip(lower=6, upper=80),
                    "sizemode": "diameter",
                    "sizeref": 2,
                    "color": PALETTE.get(endpoint, "#62748e"),
                    "opacity": 0.76,
                    "line": {"width": 1, "color": "#ffffff"},
                },
                customdata=endpoint_df[["prompt_name", "output_tokens", "tokens_per_second"]],
                hovertemplate=(
                    "input tokens: %{x}<br>"
                    "total latency: %{y:,.1f} ms<br>"
                    "prompt: %{customdata[0]}<br>"
                    "output tokens: %{customdata[1]:,.0f}<br>"
                    "tokens/sec: %{customdata[2]:,.1f}<extra></extra>"
                ),
            )
        )
    fig.update_xaxes(title_text="Input tokens")
    fig.update_yaxes(title_text="Total latency ms")
    return apply_chart_style(fig)


def latency_distribution(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for endpoint in ENDPOINT_ORDER:
        endpoint_df = df[df["endpoint"].astype(str) == endpoint]
        if endpoint_df.empty:
            continue
        fig.add_trace(
            go.Box(
                name=endpoint,
                y=endpoint_df["total_latency_ms"],
                marker_color=PALETTE.get(endpoint, "#62748e"),
                boxmean=True,
                hovertemplate="total latency: %{y:,.1f} ms<extra></extra>",
            )
        )
    fig.update_yaxes(title_text="Total latency ms")
    return apply_chart_style(fig)


def chart_panel(title: str, subtitle: str, fig: go.Figure, include_plotlyjs: bool) -> str:
    chart_html = pio.to_html(
        fig,
        include_plotlyjs="cdn" if include_plotlyjs else False,
        full_html=False,
        config={
            "displayModeBar": True,
            "responsive": True,
            "displaylogo": False,
        },
    )
    return f"""
    <section class="panel chart-panel">
      <div class="panel-heading">
        <h2>{html.escape(title)}</h2>
        <p>{html.escape(subtitle)}</p>
      </div>
      {chart_html}
    </section>
    """


def metric_card(label: str, value: str, note: str) -> str:
    return f"""
    <article class="metric-card">
      <span>{html.escape(label)}</span>
      <strong>{html.escape(value)}</strong>
      <small>{html.escape(note)}</small>
    </article>
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
    df = normalize_dataframe(df)
    summary = grouped_summary(df)
    stream_df = df[df["endpoint"].astype(str) == "generate-stream"].dropna(subset=["ttft_ms"])

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

    panels = [
        chart_panel(
            "p95 TTFT by Prompt Length",
            "First-token responsiveness for the streaming endpoint.",
            grouped_bar(summary, "p95_ttft_ms", "p95 TTFT ms", "generate-stream"),
            include_plotlyjs=True,
        ),
        chart_panel(
            "p95 Total Latency",
            "End-to-end response latency across endpoint modes.",
            grouped_bar(summary, "p95_total_latency_ms", "p95 total latency ms"),
            include_plotlyjs=False,
        ),
        chart_panel(
            "Throughput by Prompt Length",
            "Mean generated tokens per second.",
            grouped_bar(summary, "mean_tokens_per_second", "mean tokens/sec"),
            include_plotlyjs=False,
        ),
        chart_panel(
            "Prompt Size vs Latency",
            "Each point is one benchmark request; point size reflects output tokens.",
            latency_scatter(df),
            include_plotlyjs=False,
        ),
        chart_panel(
            "Latency Distribution",
            "Box plots help spot endpoint variability beyond averages.",
            latency_distribution(df),
            include_plotlyjs=False,
        ),
    ]

    return page_template(
        body=f"""
        <section class="hero">
          <div>
            <p class="eyebrow">LLM Inference Benchmark Dashboard</p>
            <h1>TTFT, Latency, and Throughput</h1>
            <p>
              Interactive Plotly dashboard generated from
              <code>{html.escape(str(input_path))}</code>. Use it to compare
              streaming and non-streaming behavior across prompt lengths.
            </p>
          </div>
        </section>

        <section class="metrics">
          {''.join(cards)}
        </section>

        <main class="grid">
          {''.join(panels)}
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
      --bg: #f5f7fb;
      --surface: #ffffff;
      --surface-2: #eef2f7;
      --text: #101828;
      --muted: #667085;
      --line: #d9e2ef;
      --accent: #2f6fed;
      --accent-2: #1fa971;
      --shadow: 0 18px 48px rgba(16, 24, 40, 0.08);
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
      background:
        linear-gradient(135deg, rgba(47, 111, 237, 0.10), rgba(31, 169, 113, 0.08)),
        var(--surface);
      border-bottom: 1px solid var(--line);
      padding: 54px 28px 38px;
    }}

    .hero > div,
    .metrics,
    .grid {{
      max-width: 1220px;
      margin: 0 auto;
    }}

    .eyebrow {{
      margin: 0 0 10px;
      color: var(--accent);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0;
    }}

    h1 {{
      max-width: 860px;
      margin: 0;
      font-size: clamp(36px, 5vw, 62px);
      line-height: 1;
      letter-spacing: 0;
    }}

    .hero p:last-child {{
      max-width: 800px;
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.65;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      padding: 24px 28px 4px;
    }}

    .metric-card,
    .panel {{
      background: rgba(255, 255, 255, 0.94);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}

    .metric-card {{
      padding: 18px;
    }}

    .metric-card span,
    .metric-card small,
    .panel-heading p {{
      color: var(--muted);
    }}

    .metric-card span {{
      display: block;
      font-size: 13px;
      font-weight: 800;
    }}

    .metric-card strong {{
      display: block;
      margin-top: 10px;
      font-size: 30px;
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
      min-width: 0;
      padding: 20px;
    }}

    .chart-panel {{
      min-height: 470px;
    }}

    .wide {{
      grid-column: 1 / -1;
    }}

    .panel-heading {{
      margin-bottom: 14px;
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
      font-weight: 800;
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
      background: #101828;
      color: #edf2f7;
      border-radius: 8px;
      padding: 18px;
      line-height: 1.55;
    }}

    @media (max-width: 900px) {{
      .metrics,
      .grid {{
        grid-template-columns: 1fr;
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
    print(f"Wrote Plotly benchmark dashboard to {output_path}")


if __name__ == "__main__":
    main()
