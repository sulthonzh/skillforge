"""Application settings.

All configuration is read from environment variables. Secrets (API keys) are
never written to disk and never logged.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_skills_dir() -> Path:
    """Default to ``~/.skillforge/skills`` (expanded)."""
    return Path.home() / ".skillforge" / "skills"


class Settings(BaseSettings):
    """Runtime configuration for the SkillForge API.

    The default provider is ``mock`` so the service runs offline with no
    configuration at all. Override via environment variables (see the root
    ``.env.example``).
    """

    model_config = SettingsConfigDict(
        env_prefix="SKILLFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- AI provider ----
    ai_provider: str = Field(
        default="mock",
        description="One of: mock | openai-compatible | ollama-local | anthropic | gemini | cohere",
    )
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_api_key: str = Field(default="")
    ollama_base_url: str = Field(default="http://localhost:11434")
    anthropic_base_url: str = Field(default="https://api.anthropic.com")
    anthropic_api_key: str = Field(default="")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com")
    gemini_api_key: str = Field(default="")
    cohere_base_url: str = Field(default="https://api.cohere.com")
    cohere_api_key: str = Field(default="")
    model: str = Field(default="gpt-4.1")

    # ---- Local install dir ----
    skills_dir: Path = Field(default_factory=_default_skills_dir)

    # ---- Server ----
    # Localhost-only by default — closes the LAN-exposure hole. Docker/the
    # `serve` command override to 0.0.0.0 explicitly when needed.
    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)

    # ---- Database ----
    db_path: Path = Field(default=Path("skillforge.db"))

    # ---- HTTP timeouts (per provider call) ----
    # A flat 60s timeout is too short for slow providers (e.g. Z.ai/GLM) when
    # the eval harness sends the full SKILL.md as context. Split the budget so
    # a fast connect fails fast, but a slow read can take up to 120s.
    request_connect_timeout: float = Field(default=10.0)
    request_read_timeout: float = Field(default=120.0)
    request_write_timeout: float = Field(default=15.0)
    request_pool_timeout: float = Field(default=10.0)

    # ---- Eval harness ----
    # Hard cap on (skill × prompt) completions per eval run, to guard spend.
    eval_max_calls: int = Field(default=50)
    # Max chars of SKILL.md to send as system prompt during eval "generate"
    # calls. The full SKILL.md can be several KB; truncating keeps the prompt
    # small so slow providers respond within the read timeout.
    eval_context_max_chars: int = Field(default=4000)

    # ---- Marketplace bridge ----
    # Origin of the (future) SkillForge Marketplace website, allowed to call the
    # local bridge after pairing. Empty = pairing disabled until set. Use the
    # magic value "stub" to enable the local offline adapter for testing.
    marketplace_origin: str = Field(default="stub")
    # Which marketplace adapter to use: "local-stub" (offline) today.
    marketplace_adapter: str = Field(default="local-stub")

    @field_validator("ai_provider", mode="after")
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        v = (v or "mock").strip().lower()
        allowed = {"mock", "openai-compatible", "ollama-local", "anthropic", "gemini", "cohere"}
        if v not in allowed:
            raise ValueError(
                f"SKILLFORGE_AI_PROVIDER must be one of {sorted(allowed)}, got {v!r}"
            )
        return v

    @field_validator("skills_dir", mode="after")
    @classmethod
    def _expand_skills_dir(cls, v: Path) -> Path:
        # Expand ``~`` if a user literally typed it via an env var.
        return Path(os.path.expanduser(str(v))).expanduser().resolve(strict=False)

    @field_validator("db_path", mode="after")
    @classmethod
    def _expand_db_path(cls, v: Path) -> Path:
        return Path(os.path.expanduser(str(v)))

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def http_timeout(self):
        """A split httpx.Timeout honoring the per-phase budget.

        Returning ``httpx.Timeout`` here (rather than a plain float) keeps
        callers terse — ``httpx.post(url, ..., timeout=settings.http_timeout)``.
        """
        import httpx

        return httpx.Timeout(
            connect=self.request_connect_timeout,
            read=self.request_read_timeout,
            write=self.request_write_timeout,
            pool=self.request_pool_timeout,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance."""
    return Settings()


def reload_settings() -> Settings:
    """Clear the settings cache and return a fresh instance (for tests)."""
    get_settings.cache_clear()
    return get_settings()
