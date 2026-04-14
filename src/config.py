from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


def llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").strip().lower()


def ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q6_K").strip()


def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
