from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient

from api.main import create_app
from test_api import FakeGenerator


def test_readiness_tracks_model_initialization():
    app = create_app()
    app.state.generator_provider = FakeGenerator
    with TestClient(app) as client:
        assert client.get("/health").json()["model_loaded"] is False
        assert client.get("/ready").status_code == 503
        assert client.post("/generate", json={"prompt": "hello"}).status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.get("/health").json()["model_loaded"] is True


def test_model_load_failure_is_recoverable_and_does_not_leak_details():
    app = create_app()

    def broken_provider():
        raise RuntimeError("internal file path and credentials must not reach clients")

    app.state.generator_provider = broken_provider
    with TestClient(app) as client:
        for path in ["/generate", "/generate-stream"]:
            response = client.post(path, json={"prompt": "hello"})
            assert response.status_code == 503
            assert "credentials" not in response.text
        assert client.get("/ready").json()["status"] == "error"
        app.state.generator_provider = FakeGenerator
        assert client.post("/generate", json={"prompt": "retry"}).status_code == 200


def test_context_rejection_returns_json_before_stream_starts():
    app = create_app()

    class LimitedGenerator(FakeGenerator):
        def validate_request(self, prompt, max_new_tokens):
            raise ValueError("Prompt plus output exceeds the context window.")

    app.state.generator_provider = LimitedGenerator
    with TestClient(app) as client:
        for path in ["/generate", "/generate-stream"]:
            response = client.post(path, json={"prompt": "too long"})
            assert response.status_code == 422
            assert response.headers["content-type"].startswith("application/json")


def test_overlapping_requests_are_rejected_and_slot_recovers():
    app = create_app()
    entered, release = Event(), Event()

    class SlowGenerator(FakeGenerator):
        def generate(self, *args):
            entered.set()
            assert release.wait(5)
            return super().generate(*args)

    app.state.generator_provider = SlowGenerator
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, "/generate", json={"prompt": "one"})
        try:
            assert entered.wait(5)
            busy = client.post("/generate-stream", json={"prompt": "two"})
            assert busy.status_code == 429
            assert busy.headers["retry-after"] == "2"
        finally:
            release.set()
        assert future.result(timeout=5).status_code == 200
        assert client.post("/generate-stream", json={"prompt": "three"}).status_code == 200
        assert client.post("/generate", json={"prompt": "four"}).status_code == 200


def test_generation_failure_releases_slot():
    app = create_app()

    class BrokenGenerator(FakeGenerator):
        def generate(self, *args):
            raise RuntimeError("internal failure")

    app.state.generator_provider = BrokenGenerator
    with TestClient(app) as client:
        for _ in range(2):
            assert client.post("/generate", json={"prompt": "hello"}).status_code == 503


def test_whitespace_prompt_is_rejected():
    app = create_app()
    app.state.generator_provider = FakeGenerator
    with TestClient(app) as client:
        assert client.post("/generate", json={"prompt": "  \n "}).status_code == 422
