"""W1.3 environment switch + deploy guards.

Env matrix (see root ``.env.example`` + ``.omo/notepads/nyayamitra/decisions.md``)::

    APP_ENV       dev | prod                      (default: dev)
    API_URL       public API origin; prod requires https://...
    FRONTEND_URL  allowed browser origin for CORS (default: Vite dev server)
    DATABASE_URL  Neon Postgres connection string (keys via env only)
    REDIS_URL     Redis connection string for the indexing queue
    LLM_PROVIDER  gemini (primary) | groq (fallback) | stub (dev, default)
    LLM_LIVE      1 to allow live LLM calls; default 0 (cache-first)
    CACHE_MODE    preindex-only (default) | live-allowed
    CRON_SECRET   bearer token for Render cron keepalive (fail-closed stub)
    GEMINI_API_KEY / GROQ_API_KEY                 (keys via env only)

Deploy rules enforced here:

* ``APP_ENV=prod`` without ``API_URL=https://...`` raises ``RuntimeError``
  at startup — fail fast instead of serving a broken deployment.
* ``LLM_LIVE`` defaults to ``0``: dev serves cached/preindex JSON without keys.
* Ollama is dev-only. No loopback default ships in this module; local devs set
  ``OLLAMA_BASE_URL`` explicitly (see root ``.env.example``). Anything that
  needs Ollama must go through :func:`ollama_base_url_or_raise`.

Explicit ``os.getenv`` + validation is used instead of
``pydantic.BaseSettings`` because ``pydantic-settings`` is not a backend
dependency; the tests hook is :func:`reload_settings`.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache

APP_ENVS: tuple[str, ...] = ("dev", "prod")
LLM_PROVIDERS: tuple[str, ...] = ("gemini", "groq", "stub")
CACHE_MODES: tuple[str, ...] = ("preindex-only", "live-allowed")


def _get_str(key: str, default: str = "") -> str:
    """Read a string env var, stripped, with dev-safe default."""
    return os.getenv(key, default).strip()


def _get_bool(key: str, default: bool = False) -> bool:
    """Read a boolean env var (1/true/yes/y/on, case-insensitive)."""
    raw: str | None = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    """Validated snapshot of the W1.3 env matrix."""

    app_env: str = "dev"
    api_url: str = ""
    frontend_url: str = "http://localhost:5173"
    database_url: str = field(default="", repr=False)
    redis_url: str = field(default="", repr=False)
    llm_provider: str = "stub"
    llm_live: bool = False
    cache_mode: str = "preindex-only"
    cron_secret: str = field(default="", repr=False)
    gemini_api_key: str = field(default="", repr=False)
    groq_api_key: str = field(default="", repr=False)

    @property
    def is_prod(self) -> bool:
        """Whether this process runs in production mode."""
        return self.app_env == "prod"

    @property
    def has_gemini_key(self) -> bool:
        """Presence (never the value) of the Gemini key."""
        return bool(self.gemini_api_key)

    @property
    def has_groq_key(self) -> bool:
        """Presence (never the value) of the Groq key."""
        return bool(self.groq_api_key)

    def validate(self) -> Settings:
        """Enforce deploy guards; raise RuntimeError on misconfiguration."""
        if self.app_env not in APP_ENVS:
            raise RuntimeError(
                f"APP_ENV must be one of {list(APP_ENVS)}; got {self.app_env!r}."
            )
        if self.llm_provider not in LLM_PROVIDERS:
            raise RuntimeError(
                f"LLM_PROVIDER must be one of {list(LLM_PROVIDERS)}; got {self.llm_provider!r}."
            )
        if self.cache_mode not in CACHE_MODES:
            raise RuntimeError(
                f"CACHE_MODE must be one of {list(CACHE_MODES)}; got {self.cache_mode!r}."
            )
        if self.is_prod and not self.api_url.lower().startswith("https://"):
            raise RuntimeError(
                "APP_ENV=prod requires API_URL=https://... "
                f"(got {self.api_url!r}); refusing to boot on http/empty origin."
            )
        return self


def load_settings() -> Settings:
    """Build a validated :class:`Settings` from the current environment."""
    return Settings(
        app_env=_get_str("APP_ENV", "dev").lower() or "dev",
        api_url=_get_str("API_URL", ""),
        frontend_url=_get_str("FRONTEND_URL", "http://localhost:5173")
        or "http://localhost:5173",
        database_url=_get_str("DATABASE_URL", ""),
        redis_url=_get_str("REDIS_URL", ""),
        llm_provider=_get_str("LLM_PROVIDER", "stub").lower() or "stub",
        llm_live=_get_bool("LLM_LIVE", False),
        cache_mode=_get_str("CACHE_MODE", "preindex-only").lower() or "preindex-only",
        cron_secret=_get_str("CRON_SECRET", ""),
        gemini_api_key=_get_str("GEMINI_API_KEY", ""),
        groq_api_key=_get_str("GROQ_API_KEY", ""),
    ).validate()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide cached settings; call after env is final."""
    return load_settings()


def reload_settings() -> Settings:
    """Drop the cache and re-read the environment (tests hook)."""
    get_settings.cache_clear()
    return get_settings()


def ollama_base_url_or_raise(action: str = "ollama") -> str:
    """Dev-only Ollama gate: return ``OLLAMA_BASE_URL`` or raise.

    Raises in prod always (Ollama is never reachable from Vercel/Render),
    and in dev when ``OLLAMA_BASE_URL`` is unset — local devs opt in via
    root ``.env.example``. Keeps loopback defaults out of the prod path.
    """
    if _get_str("APP_ENV", "dev").lower() == "prod":
        raise RuntimeError(
            f"Ollama is dev-only and disabled when APP_ENV=prod (during {action})."
        )
    base: str = _get_str("OLLAMA_BASE_URL", "")
    if not base:
        raise RuntimeError(
            f"OLLAMA_BASE_URL is not set (during {action}). "
            "Local dev only: set it explicitly from root .env.example."
        )
    return base


def cron_authorized(
    authorization: str | None, settings: Settings | None = None
) -> bool:
    """Fail-closed bearer check stub for the Render cron keepalive (W1.4).

    Returns ``True`` only when ``CRON_SECRET`` is configured and the header
    equals ``Bearer <secret>`` (constant-time compare). ``False`` otherwise,
    including when no secret is configured.
    """
    active: Settings = settings or get_settings()
    if not active.cron_secret:
        return False
    if not authorization or not authorization.startswith("Bearer "):
        return False
    presented: str = authorization[len("Bearer ") :].strip()
    return secrets.compare_digest(presented, active.cron_secret)
