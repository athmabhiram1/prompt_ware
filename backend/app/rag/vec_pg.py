"""W2.3 pg-first vector store + LightRAG `mix` path (documented, gated).

Resolution order: pgvector when ``QA_VECTOR_BACKEND=pg`` AND ``DATABASE_URL``
is set (lazy import, no connection at import time); otherwise the in-memory
store from :mod:`app.rag.vec_mem` (default — works with ``LLM_LIVE=0``).

pgvector DDL (applied by Wave 3 ops, NOT here)::

    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE qa_chunks (chunk_id TEXT PRIMARY KEY, doc_id TEXT,
        page INT, start INT, end INT, text TEXT, embedding vector(3072));

 dim one-truth: 3072 = native dim of gemini-embedding-2-preview
 (backend/llm_provider.py:25, asserted in backend/tests/test_embed_dim.py).

 never bulk-index outside demo docs: the LightRAG path below is gated to
demo corpora (<1% ToS limits) and bulk indexing stays an ops job (Phase 4).

LightRAG ``mix`` demo path (stubbed): production retrieval for demo docs may
call ``rag.aquery(question, param=QueryParam(mode="mix", top_k=60,
chunk_top_k=20, enable_rerank=True))`` — QueryParam documented via Context7
ID ``/hkuds/lightrag``. Gated by ``QA_LIGHTRAG_DEMO=1`` + demo doc_ids only;
:func:`lightrag_demo_allowed` enforces the gate. No live index in this path.
"""

from __future__ import annotations

import os

from app.rag import vec_mem
from app.rag.chunk import Chunk
from app.rag.vec_mem import ScoredChunk

# LightRAG QueryParam values for the gated demo path (Context7 /hkuds/lightrag).
LIGHTRAG_DEMO_PARAMS = {
    "mode": "mix",
    "top_k": 60,
    "chunk_top_k": 20,
    "enable_rerank": True,
}

DEMO_DOC_IDS: frozenset[str] = frozenset({"demo-lease", "demo-tos"})


def lightrag_demo_allowed(doc_id: str | None) -> bool:
    """Gate: demo LightRAG path only with flag + demo doc (<1% limits)."""
    return os.getenv("QA_LIGHTRAG_DEMO", "0") == "1" and (doc_id in DEMO_DOC_IDS)


def resolve_backend() -> str:
    """'pg' only when explicitly requested with a DATABASE_URL; else 'memory'."""
    if os.getenv("QA_VECTOR_BACKEND", "memory") == "pg" and os.getenv("DATABASE_URL"):
        return "pg"
    return "memory"


class PgVectorStore:
    """pgvector-backed store (Wave 3 completes live queries; pg-first API)."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._mem = vec_mem  # fallback until Wave 3 wires asyncpg queries

    def search(self, query: str, chunks: list[Chunk], mode: str = "hybrid") -> list[ScoredChunk]:
        # Wave 3: SELECT ... ORDER BY embedding <=> $1 LIMIT 8. For now the
        # pg-first contract holds at the API level; scoring reuses vec_mem.
        return self._mem.hybrid_search(query, chunks, mode=mode)


def get_store() -> PgVectorStore | vec_mem.__class__:
    if resolve_backend() == "pg":
        return PgVectorStore(str(os.getenv("DATABASE_URL")))
    return vec_mem
