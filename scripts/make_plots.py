from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("plots/.matplotlib-cache").resolve()))
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def save_barplot(df: pd.DataFrame, metric: str, title: str, output_path: Path) -> None:
    plt.figure(figsize=(9, 5))
    sns.barplot(data=df, x="prompt_name", y=metric, hue="endpoint", errorbar="sd")
    plt.title(title)
    plt.xlabel("Prompt length")
    plt.ylabel(metric)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="benchmark_results/results.csv")
    parser.add_argument("--output-dir", default="plots")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    save_barplot(
        df.dropna(subset=["ttft_ms"]),
        "ttft_ms",
        "TTFT by Prompt Length",
        output_dir / "ttft_by_prompt_length.png",
    )
    save_barplot(
        df,
        "total_latency_ms",
        "Total Latency by Prompt Length",
        output_dir / "total_latency_by_prompt_length.png",
    )
    save_barplot(
        df,
        "tokens_per_second",
        "Tokens Per Second by Prompt Length",
        output_dir / "tokens_per_second.png",
    )

    print(f"Wrote plots to {output_dir}")


if __name__ == "__main__":
    main()
