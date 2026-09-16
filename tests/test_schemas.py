import pytest
from pydantic import ValidationError

from api.schemas import GenerateRequest


def test_generate_request_rejects_empty_prompt() -> None:
    with pytest.raises(ValidationError):
        GenerateRequest(prompt="")


def test_generate_request_rejects_too_many_tokens() -> None:
    with pytest.raises(ValidationError):
        GenerateRequest(prompt="hello", max_new_tokens=1000)


def test_generate_request_defaults() -> None:
    request = GenerateRequest(prompt="hello")

    assert request.max_new_tokens == 80
    assert request.temperature == 0.7
