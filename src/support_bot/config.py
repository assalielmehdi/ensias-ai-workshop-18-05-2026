"""Configuration loaded from environment variables / .env file.

We use pydantic-settings so:
- Types are validated at startup (no silent string-vs-int bugs).
- Defaults are explicit.
- Reading from .env is automatic.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for the support bot."""

    # Provider mode. "mock" lets the repo run without an API key.
    llm_mode: Literal["mock", "openrouter", "openai"] = "mock"

    # API key for the chosen provider. Ignored in mock mode.
    llm_api_key: str = ""

    # OpenAI-compatible base URL. OpenRouter is the default.
    llm_base_url: str = "https://openrouter.ai/api/v1"

    # Default model identifier.
    llm_model: str = "deepseek/deepseek-v3.2"

    # Sampling temperature.
    llm_temperature: float = 0.2

    # Hard cap on agent loop iterations.
    agent_max_iterations: int = 6

    # Logging verbosity.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Module-level singleton: import this from anywhere.
settings = Settings()
