from src.metrics import LatencyMetrics, percentile, summarize_latency


def test_latency_metrics_tokens_per_second() -> None:
    metrics = LatencyMetrics(input_tokens=10, output_tokens=25, total_latency_ms=500)

    assert metrics.tokens_per_second == 50


def test_percentile() -> None:
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([1, 2, 3, 4, 5], 95) == 4.8


def test_summarize_latency_empty() -> None:
    assert summarize_latency([]) == {"mean": 0.0, "p50": 0.0, "p95": 0.0}
