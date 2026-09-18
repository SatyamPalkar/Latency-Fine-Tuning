import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setattr(app.state, "generator_provider", FakeGenerator)


class FakeGenerator:
    def generate(self, prompt: str, max_new_tokens: int, temperature: float) -> dict[str, object]:
        return {
            "text": f"fake response for {prompt}",
            "model_name": "fake-model",
            "device": "cpu",
            "input_tokens": 3,
            "output_tokens": 4,
            "ttft_ms": 5.0,
            "total_latency_ms": 12.5,
            "tokens_per_second": 320.0,
        }

    def stream(self, prompt: str, max_new_tokens: int, temperature: float):
        yield 'event: token\ndata: {"text": "fake"}\n\n'
        yield (
            'event: metrics\n'
            'data: {"model_name": "fake-model", "device": "cpu", "input_tokens": 3, '
            '"output_tokens": 1, "ttft_ms": 10.0, "total_latency_ms": 20.0, '
            '"tokens_per_second": 50.0}\n\n'
        )


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_loaded": True}


def test_generate() -> None:
    client = TestClient(app)

    response = client.post("/generate", json={"prompt": "hello", "max_new_tokens": 8})

    assert response.status_code == 200
    assert response.json()["model_name"] == "fake-model"
    assert response.json()["ttft_ms"] == 5.0


def test_generate_rejects_empty_prompt() -> None:
    client = TestClient(app)

    response = client.post("/generate", json={"prompt": ""})

    assert response.status_code == 422


def test_frontend_and_assets() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="prompt-form"' in response.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/benchmarks").status_code == 200


def test_generate_stream() -> None:
    response = TestClient(app).post("/generate-stream", json={"prompt": "hello"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: token\ndata: {"text": "fake"}' in response.text
    assert '"ttft_ms": 10.0' in response.text
