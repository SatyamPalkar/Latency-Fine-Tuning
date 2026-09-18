import json
from types import SimpleNamespace

import pytest
import torch

from src import generation


class FakeTokenizer:
    eos_token_id = 99

    def decode(self, tokens, **kwargs):
        return "".join({4: "hel", 5: "lo ", 6: "world"}.get(int(t), "") for t in tokens)


class FakeModel:
    def __init__(self, tokens=(4, 5, 6), fail=False):
        self.tokens = tokens
        self.fail = fail
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        assert torch.is_inference_mode_enabled()
        streamer = kwargs["streamer"]
        streamer.put(kwargs["input_ids"])
        if self.fail:
            raise RuntimeError("Simulated model failure")
        for token in self.tokens:
            streamer.put(torch.tensor([token]))
        streamer.end()
        return torch.tensor([[1, 2, *self.tokens]])


@pytest.fixture
def generator(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(
        generation, "load_model_and_tokenizer",
        lambda name: (model, FakeTokenizer(), "cpu"),
    )
    instance = generation.LLMGenerator("fake-model")
    monkeypatch.setattr(instance, "_inputs", lambda prompt: {"input_ids": torch.tensor([[1, 2]])})
    ticks = iter([1.0, 1.1, 1.5])
    monkeypatch.setattr(generation, "time", SimpleNamespace(perf_counter=lambda: next(ticks)))
    return instance


def test_generate_measures_first_token_and_decodes_only_output(generator):
    result = generator.generate("arbitrary prompt", 3, 0)
    assert result["text"] == "hello world"
    assert result["input_tokens"] == 2
    assert result["output_tokens"] == 3
    assert result["ttft_ms"] == pytest.approx(100)
    assert result["total_latency_ms"] == pytest.approx(500)
    assert result["tokens_per_second"] == pytest.approx(6)
    assert generator.model.kwargs["do_sample"] is False
    assert "temperature" not in generator.model.kwargs


def test_stream_measures_token_before_buffered_text(generator):
    events = list(generator.stream("hello", 3, 0.7))
    metrics = json.loads(events[-1].split("data: ")[1])
    assert metrics["text"] == "hello world"
    assert metrics["output_tokens"] == 3
    assert metrics["ttft_ms"] == pytest.approx(100)
    assert metrics["total_latency_ms"] == pytest.approx(500)
    assert generator.model.kwargs["temperature"] == 0.7


def test_timed_streamer_ignores_prompt_and_counts_special_tokens():
    streamer = generation.TimedStreamer(FakeTokenizer())
    streamer.put(torch.tensor([[1, 2]]))
    assert streamer.first_token_at is None
    streamer.put(torch.tensor([4]))
    first_token_at = streamer.first_token_at
    assert next(streamer) == ""  # The first token has not formed a complete word.
    streamer.put(torch.tensor([99]))
    assert streamer.first_token_at == first_token_at
    assert streamer.output_tokens == 2


def test_stream_failure_unblocks_and_emits_error(generator):
    generator.model.fail = True
    events = list(generator.stream("hello", 3, 0))
    assert len(events) == 1
    assert events[0].startswith("event: error")


def test_no_generated_tokens_has_null_ttft(generator):
    generator.model.tokens = ()
    result = generator.generate("hello", 3, 0)
    assert result["ttft_ms"] is None
    assert result["output_tokens"] == 0
    assert result["text"] == ""
