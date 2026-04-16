from __future__ import annotations

import os

from dotenv import load_dotenv


### Load environment variables once when the config module is imported.
###############################################################################
load_dotenv()


### Return the configured extraction provider name.
###############################################################################
def llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "ollama").strip().lower()


### Return the Ollama model identifier used for local extraction.
###############################################################################
def ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q6_K").strip()


### Return the Ollama base URL with trailing slashes normalized away.
###############################################################################
def ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
