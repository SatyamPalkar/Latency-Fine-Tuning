import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_name: str = os.getenv("MODEL_NAME", "distilgpt2")
    model_revision: str | None = os.getenv("MODEL_REVISION") or None
    max_new_tokens: int = int(os.getenv("MAX_NEW_TOKENS", "256"))
    device: str = os.getenv("DEVICE", "auto")
    generation_timeout_seconds: float = float(os.getenv("GENERATION_TIMEOUT_SECONDS", "45"))
    preload_model: bool = os.getenv("PRELOAD_MODEL", "false").lower() == "true"

    def __post_init__(self):
        if not 1 <= self.max_new_tokens <= 256:
            raise ValueError("MAX_NEW_TOKENS must be between 1 and 256")
        if not 1 <= self.generation_timeout_seconds <= 120:
            raise ValueError("GENERATION_TIMEOUT_SECONDS must be between 1 and 120")


settings = Settings()
