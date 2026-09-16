from __future__ import annotations

from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.config import settings


def resolve_device(device_setting: str) -> str:
    if device_setting != "auto":
        return device_setting
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_model_and_tokenizer(model_name: Optional[str] = None, device: Optional[str] = None):
    selected_model = model_name or settings.model_name
    selected_device = resolve_device(device or settings.device)

    tokenizer = AutoTokenizer.from_pretrained(selected_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(selected_model)
    model.to(selected_device)
    model.eval()
    return model, tokenizer, selected_device
