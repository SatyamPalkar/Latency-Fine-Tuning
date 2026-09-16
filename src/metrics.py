from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Dict, Iterable, Optional, Union


@dataclass(frozen=True)
class LatencyMetrics:
    input_tokens: int
    output_tokens: int
    total_latency_ms: float
    ttft_ms: Optional[float] = None

    @property
    def tokens_per_second(self) -> float:
        seconds = self.total_latency_ms / 1000
        if seconds <= 0:
            return 0.0
        return self.output_tokens / seconds

    def to_dict(self) -> Dict[str, Union[float, int, None]]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "ttft_ms": self.ttft_ms,
            "total_latency_ms": self.total_latency_ms,
            "tokens_per_second": self.tokens_per_second,
        }


def percentile(values: Iterable[float], pct: float) -> float:
    sorted_values = sorted(values)
    if not sorted_values:
        return 0.0
    if pct <= 0:
        return sorted_values[0]
    if pct >= 100:
        return sorted_values[-1]
    rank = (len(sorted_values) - 1) * (pct / 100)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def summarize_latency(values: list[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0}
    return {
        "mean": mean(values),
        "p50": median(values),
        "p95": percentile(values, 95),
    }
