import json

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from scripts.run_benchmark import measure, sse_events, summarize, validate_metrics
from test_api import FakeGenerator

VALID = {"model_name": "test", "device": "cpu", "input_tokens": 2, "output_tokens": 3,
         "ttft_ms": 10, "total_latency_ms": 20, "tokens_per_second": 150}


class Response:
    encoding = None

    def __init__(self, frames):
        self.frames = frames

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def raise_for_status(self):
        pass

    def iter_lines(self, **_):
        yield from self.frames.splitlines()


class Session:
    def __init__(self, frames):
        self.frames = frames

    def post(self, *_, **__):
        return Response(self.frames)


def test_sse_handles_comments_multiline_crlf_and_final_frame():
    frames = [": ping\r", "event: metrics\r", 'data: {"a":\r', "data: 1}\r", "\r",
              "event: token", 'data: {"text":"hello"}']
    assert list(sse_events(frames)) == [("metrics", {"a": 1}), ("token", {"text": "hello"})]


@pytest.mark.parametrize("frames", [
    'event: token\ndata: {"text":"hello"}\n\n',
    'event: error\ndata: {"message":"model failed"}\n\n',
    'event: metrics\ndata: {}\n\n',
    f'event: metrics\ndata: {json.dumps(VALID)}\n\nevent: metrics\ndata: {json.dumps(VALID)}\n\n',
])
def test_incomplete_error_or_duplicate_stream_is_not_a_successful_sample(frames):
    with pytest.raises(ValueError):
        measure(Session(frames), "http://test", "generate-stream", {}, 1)


def test_client_first_text_is_separate_from_server_token_ttft():
    frames = f'event: token\ndata: {{"text":"hello"}}\n\nevent: metrics\ndata: {json.dumps(VALID)}\n\n'
    result = measure(Session(frames), "http://test", "generate-stream", {}, 1)
    assert result["ttft_ms"] == 10
    assert 0 <= result["client_first_text_ms"] <= result["wall_latency_ms"]


@pytest.mark.parametrize("replacement", [{"ttft_ms": None}, {"ttft_ms": 21},
    {"ttft_ms": True}, {"total_latency_ms": float("nan")}, {"output_tokens": -1}])
def test_invalid_metrics_cannot_silently_enter_report(replacement):
    with pytest.raises(ValueError):
        validate_metrics({**VALID, **replacement})


def test_summary_counts_failures_without_making_them_zero_latency():
    rows = [{"prompt_name": "short", "endpoint": "generate", "success": True,
             **VALID, "wall_latency_ms": 25, "client_first_text_ms": None},
            {"prompt_name": "short", "endpoint": "generate", "success": False, "error": "timeout"}]
    group = summarize(rows)[0]
    assert (group["attempted"], group["successful"], group["failed"]) == (2, 1, 1)
    assert group["ttft_ms"]["mean"] == 10
    assert group["client_first_text_ms"] is None


def test_runtime_metadata_requires_loaded_model_and_reports_serving_process():
    app = create_app()
    app.state.generator_provider = FakeGenerator
    with TestClient(app) as client:
        assert client.get("/benchmark-info").status_code == 503
        client.post("/generate", json={"prompt": "warmup"})
        info = client.get("/benchmark-info").json()
        assert info["torch_threads"] > 0
        assert info["torch"] and info["transformers"] and info["python"]
