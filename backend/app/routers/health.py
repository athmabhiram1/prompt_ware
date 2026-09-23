"""W1.3 health contract: ``/health``, ``/health/db``, ``/ready``.

Shapes (stable — W1.4 Render + Wave 2 depend on them)::

    GET /health     -> {status, env, llm_live, provider, cache_mode}
    GET /health/db  -> {status, env, checks: {neo4j, postgres, redis}}
    GET /ready      -> {ready, env, preindex: {present, bundles, names}, llm_live}

Nothing here ever leaks secrets: only hostnames, booleans and latencies are
returned. Live LLM/provider SDKs are never imported — reachability is a plain
TCP dial with a short timeout, safe to call from Render free-tier cron.
"""

from __future__ import annotations

import socket
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_DIR = _BACKEND_DIR.parent

_PREINDEX_CANDIDATES: tuple[Path, ...] = (
    _REPO_DIR / "data" / "preindex",
    _BACKEND_DIR / "data" / "preindex",
)

_DIAL_TIMEOUT_S = 2.0


class HealthResponse(BaseModel):
    status: str
    env: str
    llm_live: bool
    provider: str
    cache_mode: str


class DbTargetStatus(BaseModel):
    configured: bool
    reachable: bool | None = None
    host: str | None = None
    latency_ms: float | None = None
    detail: str | None = None


class DbHealthResponse(BaseModel):
    status: str
    env: str
    checks: dict[str, DbTargetStatus]


class PreindexStatus(BaseModel):
    present: bool
    bundles: int
    names: list[str]


class ReadyResponse(BaseModel):
    ready: bool
    env: str
    llm_live: bool
    preindex: PreindexStatus


def _tcp_reachable(host: str, port: int, timeout_s: float = _DIAL_TIMEOUT_S) -> tuple[bool, float, str]:
    """Dial host:port; return (reachable, latency_ms, detail) without secrets."""
    start: float = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            elapsed_ms: float = (time.perf_counter() - start) * 1000.0
            return True, round(elapsed_ms, 1), "tcp connect ok"
    except OSError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return False, round(elapsed_ms, 1), f"{type(exc).__name__}: {str(exc)[:120]}"


def _check_url_target(raw_url: str, default_port: int) -> DbTargetStatus:
    """TCP reachability for a URL env var; reports host only, never credentials."""
    if not raw_url:
        return DbTargetStatus(configured=False)
    try:
        parsed = urlparse(raw_url)
        host: str = parsed.hostname or ""
        port: int = parsed.port or default_port
        if not host:
            return DbTargetStatus(configured=True, reachable=False, detail="unparseable host")
        ok, latency_ms, detail = _tcp_reachable(host, port)
        return DbTargetStatus(
            configured=True, reachable=ok, host=host, latency_ms=latency_ms, detail=detail
        )
    except (ValueError, OSError) as exc:
        return DbTargetStatus(configured=True, reachable=False, detail=f"{type(exc).__name__}")


def _check_neo4j() -> DbTargetStatus:
    """Reachability across Aura/local Neo4j candidates (first reachable wins)."""
    try:
        from neo4j_connection import _candidate_targets
    except ImportError as exc:
        return DbTargetStatus(configured=False, detail=f"driver unavailable: {type(exc).__name__}")
    try:
        targets = _candidate_targets()
    except (AttributeError, RuntimeError, ValueError) as exc:
        return DbTargetStatus(configured=False, detail=f"no targets: {str(exc)[:120]}")
    if not targets:
        return DbTargetStatus(configured=False, detail="no Neo4j targets configured")
    last_detail: str = "unreachable"
    for target in targets:
        host_part: str = target.uri.split("://")[-1]
        host: str = host_part.split(":")[0] or ""
        try:
            port: int = int(host_part.split(":")[-1]) if ":" in host_part else 7687
        except ValueError:
            port = 7687
        if not host:
            continue
        ok, latency_ms, detail = _tcp_reachable(host, port)
        last_detail = detail
        if ok:
            return DbTargetStatus(
                configured=True,
                reachable=True,
                host=f"{target.name}@{host}",
                latency_ms=latency_ms,
                detail=detail,
            )
    return DbTargetStatus(configured=True, reachable=False, detail=last_detail)


def _scan_preindex() -> PreindexStatus:
    """Report committed ``preindex`` JSON bundles (W1.4/W2 fill these)."""
    names: list[str] = []
    for directory in _PREINDEX_CANDIDATES:
        try:
            if directory.is_dir():
                names.extend(sorted(p.name for p in directory.glob("*.json") if p.is_file()))
        except OSError:
            continue
    unique: list[str] = sorted(set(names))
    return PreindexStatus(present=bool(unique), bundles=len(unique), names=unique[:50])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: 200 when the process boots and config validates."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        env=settings.app_env,
        llm_live=settings.llm_live,
        provider=settings.llm_provider,
        cache_mode=settings.cache_mode,
    )


@router.get("/health/db", response_model=DbHealthResponse)
async def health_db() -> DbHealthResponse:
    """Readiness of datastores (Aura/Neon/Redis) without leaking secrets."""
    settings = get_settings()
    neo4j: DbTargetStatus = _check_neo4j()
    postgres: DbTargetStatus = _check_url_target(settings.database_url, 5432)
    redis: DbTargetStatus = _check_url_target(settings.redis_url, 6379)
    reachable_flags: list[bool] = [
        check.reachable is True for check in (neo4j, postgres, redis) if check.configured
    ]
    status: str = "ok"
    if reachable_flags and not all(reachable_flags):
        status = "degraded"
    if not reachable_flags:
        status = "ok"
    return DbHealthResponse(
        status=status,
        env=settings.app_env,
        checks={"neo4j": neo4j, "postgres": postgres, "redis": redis},
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """Ready when preindex bundles are present (cache-first serving)."""
    settings = get_settings()
    preindex: PreindexStatus = _scan_preindex()
    return ReadyResponse(
        ready=preindex.present,
        env=settings.app_env,
        llm_live=settings.llm_live,
        preindex=preindex,
    )
