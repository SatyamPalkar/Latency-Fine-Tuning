import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_name: str = os.getenv("MODEL_NAME", "distilgpt2")
    max_new_tokens: int = int(os.getenv("MAX_NEW_TOKENS", "80"))
    device: str = os.getenv("DEVICE", "auto")


settings = Settings()
