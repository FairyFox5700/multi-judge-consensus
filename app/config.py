"""Application configuration.

All settings are sourced from environment variables so the app can run in three modes
without any code changes:

1. Demo mode (default, no keys set)   -> deterministic mock judges, zero external calls.
2. Partial mode (some keys set)       -> real judges for configured providers, mock for the rest.
3. Full mode (all keys set)           -> GPT-4o, GPT-4o-mini and Claude all call live APIs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    # OpenAI / Azure OpenAI
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    azure_openai_endpoint: str = field(default_factory=lambda: _env("AZURE_OPENAI_ENDPOINT"))
    azure_openai_api_key: str = field(default_factory=lambda: _env("AZURE_OPENAI_API_KEY"))
    azure_openai_api_version: str = field(
        default_factory=lambda: _env("AZURE_OPENAI_API_VERSION", "2024-10-21")
    )
    gpt4o_deployment: str = field(default_factory=lambda: _env("GPT4O_DEPLOYMENT", "gpt-4o"))
    gpt4o_mini_deployment: str = field(
        default_factory=lambda: _env("GPT4O_MINI_DEPLOYMENT", "gpt-4o-mini")
    )

    # Anthropic
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    claude_model: str = field(
        default_factory=lambda: _env("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
    )

    # Consensus behaviour
    review_threshold: float = field(
        default_factory=lambda: float(_env("REVIEW_THRESHOLD", "3"))
    )
    # Force demo mode even if keys are present (useful for CI / portfolio demos).
    force_demo_mode: bool = field(
        default_factory=lambda: _env("FORCE_DEMO_MODE", "false").lower() in ("1", "true", "yes")
    )

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key) or bool(
            self.azure_openai_endpoint and self.azure_openai_api_key
        )

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
