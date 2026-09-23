"""Storage-selection matrix (T5 PG cutover): TDD-first.

Asserts `_build_rag` storage selection across 4 env states, with
monkeypatched env + fake hosts and NO connections:

- PG env -> PGKVStorage / PGVectorStorage / PGDocStatusStorage + PGTableGraphStorage
- PG + Mongo -> PG wins (graph is PGTableGraphStorage, not Neo4j/NetworkX)
- Mongo-only -> Mongo trio (regression; graph keeps the Neo4j/NetworkX fork)
- neither -> JSON trio + NetworkX (regression)

Bridge unit tests: DATABASE_URL parse, no-clobber of existing POSTGRES_*,
and the pooled-URL statement-cache knob documented on the bridge.

No live PG/Aura calls: LightRAG ctor + provider helpers are stubbed, socket
probes are monkeypatched, all hosts/URLs are fake.
"""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# request_queue imports redis.asyncio at module import; redis is not installed
# in this env (pre-existing: backend/smoke_test.py also fails to collect).
# Stub it so this matrix stays hermetic — no connections are ever made.
if "redis" not in sys.modules:
    try:
        import redis  # noqa: F401
    except ModuleNotFoundError:
        _redis_stub = ModuleType("redis")
        _redis_async_stub = ModuleType("redis.asyncio")
        _redis_async_stub.Redis = object  # type: ignore[attr-defined]
        _redis_stub.asyncio = _redis_async_stub  # type: ignore[attr-defined]
        sys.modules["redis"] = _redis_stub
        sys.modules["redis.asyncio"] = _redis_async_stub

import lightrag_engine as _le


def _stub_engine(monkeypatch, *, neo4j_reachable=False):
    """Stub provider helpers + LightRAG ctor; capture storage kwargs."""
    captured = {}

    class _FakeRAG:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    async def _fake_embed(texts):
        return []

    async def _fake_llm(*args, **kwargs):
        return ""

    monkeypatch.setattr(_le, "LightRAG", _FakeRAG)
    monkeypatch.setattr(_le, "get_llm_func", lambda: (_fake_llm, "fake-model"))
    monkeypatch.setattr(_le, "get_embedding_func", lambda: _fake_embed)
    monkeypatch.setattr(_le, "get_active_rag_storage_dir", lambda: Path("/tmp/fake-rag"))
    monkeypatch.setattr(_le, "_neo4j_available", lambda: neo4j_reachable)
    monkeypatch.setattr(_le, "_resolve_neo4j_env", lambda: None)
    return captured


def _clear_storage_env(monkeypatch):
    for key in (
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD",
        "POSTGRES_DATABASE", "POSTGRES_SSL_MODE", "DATABASE_URL", "MONGO_URI",
    ):
        monkeypatch.delenv(key, raising=False)


def test_pg_env_selects_pg_trio_plus_pgtable_graph(monkeypatch):
    _clear_storage_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_USER", "fake_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "fake_pass")
    monkeypatch.setenv("POSTGRES_DATABASE", "fake_db")
    monkeypatch.setenv("POSTGRES_HOST", "fake-pg-host")
    captured = _stub_engine(monkeypatch)
    _le._build_rag("test_co")
    assert captured["kv_storage"] == "PGKVStorage"
    assert captured["vector_storage"] == "PGVectorStorage"
    assert captured["doc_status_storage"] == "PGDocStatusStorage"
    assert captured["graph_storage"] == "PGTableGraphStorage"


def test_pg_url_only_selects_pg_via_bridge(monkeypatch):
    _clear_storage_env(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://url_user:url_pass@fake-pg-host:5432/url_db?pgbouncer=true",
    )
    captured = _stub_engine(monkeypatch)
    _le._build_rag("test_co")
    assert captured["kv_storage"] == "PGKVStorage"
    assert captured["vector_storage"] == "PGVectorStorage"
    assert captured["doc_status_storage"] == "PGDocStatusStorage"
    assert captured["graph_storage"] == "PGTableGraphStorage"


def test_pg_plus_mongo_pg_wins(monkeypatch):
    _clear_storage_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_USER", "fake_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "fake_pass")
    monkeypatch.setenv("POSTGRES_DATABASE", "fake_db")
    monkeypatch.setenv("MONGO_URI", "mongodb://fake-mongo-host:27017/fake")
    captured = _stub_engine(monkeypatch, neo4j_reachable=True)
    _le._build_rag("test_co")
    assert captured["kv_storage"] == "PGKVStorage"
    assert captured["vector_storage"] == "PGVectorStorage"
    assert captured["doc_status_storage"] == "PGDocStatusStorage"
    assert captured["graph_storage"] == "PGTableGraphStorage"


def test_mongo_only_selects_mongo_trio_regression(monkeypatch):
    _clear_storage_env(monkeypatch)
    monkeypatch.setenv("MONGO_URI", "mongodb://fake-mongo-host:27017/fake")
    captured = _stub_engine(monkeypatch)
    _le._build_rag("test_co")
    assert captured["kv_storage"] == "MongoKVStorage"
    assert captured["vector_storage"] == "MongoVectorDBStorage"
    assert captured["doc_status_storage"] == "MongoDocStatusStorage"
    assert captured["graph_storage"] == "NetworkXStorage"


def test_neither_selects_json_trio_plus_networkx_regression(monkeypatch):
    _clear_storage_env(monkeypatch)
    captured = _stub_engine(monkeypatch)
    _le._build_rag("test_co")
    assert captured["kv_storage"] == "JsonKVStorage"
    assert captured["vector_storage"] == "NanoVectorDBStorage"
    assert captured["doc_status_storage"] == "JsonDocStatusStorage"
    assert captured["graph_storage"] == "NetworkXStorage"


def test_bridge_parses_database_url(monkeypatch):
    _clear_storage_env(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://bridge_user:bridge_pass@fake-pg-host:5433/bridge_db",
    )
    _le._bridge_database_url_to_postgres_env()
    import os

    assert os.getenv("POSTGRES_HOST") == "fake-pg-host"
    assert os.getenv("POSTGRES_PORT") == "5433"
    assert os.getenv("POSTGRES_USER") == "bridge_user"
    assert os.getenv("POSTGRES_PASSWORD") == "bridge_pass"
    assert os.getenv("POSTGRES_DATABASE") == "bridge_db"
    assert os.getenv("POSTGRES_SSL_MODE") == "require"


def test_bridge_never_clobbers_existing_postgres_vars(monkeypatch):
    _clear_storage_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_HOST", "keep-me-host")
    monkeypatch.setenv("POSTGRES_PORT", "5439")
    monkeypatch.setenv("POSTGRES_USER", "keep-me-user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "keep-me-pass")
    monkeypatch.setenv("POSTGRES_DATABASE", "keep-me-db")
    monkeypatch.setenv("POSTGRES_SSL_MODE", "verify-full")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://other:other@fake-pg-host:5432/other_db",
    )
    _le._bridge_database_url_to_postgres_env()
    import os

    assert os.getenv("POSTGRES_HOST") == "keep-me-host"
    assert os.getenv("POSTGRES_PORT") == "5439"
    assert os.getenv("POSTGRES_USER") == "keep-me-user"
    assert os.getenv("POSTGRES_PASSWORD") == "keep-me-pass"
    assert os.getenv("POSTGRES_DATABASE") == "keep-me-db"
    assert os.getenv("POSTGRES_SSL_MODE") == "verify-full"


def test_bridge_documents_pooled_statement_cache_knob():
    doc = (_le._bridge_database_url_to_postgres_env.__doc__ or "")
    assert "statement_cache_size=0" in doc or "statement-cache" in doc


def test_postgres_configured_accepts_trio_or_url(monkeypatch):
    _clear_storage_env(monkeypatch)
    assert _le._postgres_configured() is False
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DATABASE", "d")
    assert _le._postgres_configured() is True
    _clear_storage_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@fake-host:5432/d")
    assert _le._postgres_configured() is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
