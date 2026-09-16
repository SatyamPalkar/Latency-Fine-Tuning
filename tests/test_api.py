from fastapi.testclient import TestClient

from api.main import app


class FakeGenerator:
    def generate(self, prompt: str, max_new_tokens: int, temperature: float) -> dict[str, object]:
        return {
            "text": f"fake response for {prompt}",
            "model_name": "fake-model",
            "device": "cpu",
            "input_tokens": 3,
            "output_tokens": 4,
            "ttft_ms": None,
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
    app.state.generator_provider = FakeGenerator
    client = TestClient(app)

    response = client.post("/generate", json={"prompt": "hello", "max_new_tokens": 8})

    assert response.status_code == 200
    assert response.json()["model_name"] == "fake-model"
    app.state.generator_provider = FakeGenerator


def test_generate_rejects_empty_prompt() -> None:
    app.state.generator_provider = FakeGenerator
    client = TestClient(app)

    response = client.post("/generate", json={"prompt": ""})

    assert response.status_code == 422
