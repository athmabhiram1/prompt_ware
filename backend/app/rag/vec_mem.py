"""W2.3 hybrid retriever — 0.65*semantic + 0.35*BM25, top-8 retrieve, top-4 keep.

CiteGuard RAG section 2.4 numbers, verbatim. Paths selectable per request:
``hybrid`` (default), ``lexical``-only, ``semantic``-only.

Embeddings are pluggable via ``EmbedFn``: production uses Gemini embeddings
(768d MRL-truncated) with a MiniLM (all-MiniLM-L6-v2, 384d) fallback; tests
and ``LLM_LIVE=0`` use :func:`stub_embed`, a deterministic feature-hash
bag-of-words stand-in (L2-normalized, cosine in [0,1]) — no live keys.

Rerank: CiteGuard section 2.6 found the heuristic reranker REDUCED
controlled performance, so reranking is OFF (identity pass-through that only
truncates to top-4). Production slot documented for ``bge-reranker-v2-m3``
cross-encoder behind an eval gate — NOT implemented here per spec.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.rag.chunk import Chunk

SEMANTIC_WEIGHT = 0.65
LEXICAL_WEIGHT = 0.35
RETRIEVE_TOPK = 8
RERANK_TOPK = 4
EMBED_DIM = 256

EmbedFn = Callable[[str], Sequence[float]]

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def word_tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def stub_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic test embedding: hashed bag-of-words, L2-normalized."""
    vec = [0.0] * dim
    for tok in word_tokens(text):
        vec[int(hashlib.md5(tok.encode()).hexdigest(), 16) % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity clamped to [0, 1] (negative sims count as 0)."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _idf_weights(docs: list[list[str]]) -> dict[str, float]:
    df: Counter[str] = Counter()
    for toks in docs:
        df.update(set(toks))
    n = max(1, len(docs))
    return {tok: math.log((n + 1) / (freq + 1)) + 1.0 for tok, freq in df.items()}


def lexical_score(query_toks: list[str], doc_toks: list[str], idf: dict[str, float]) -> float:
    """IDF-weighted query-term recall in [0, 1] (BM25-style, length-free)."""
    need = set(query_toks)
    if not need:
        return 0.0
    have = set(doc_toks)
    denom = sum(idf.get(t, 1.0) for t in need)
    return sum(idf.get(t, 1.0) for t in need & have) / denom if denom else 0.0


@dataclass
class ScoredChunk:
    chunk: Chunk
    semantic: float
    lexical: float
    score: float


def _fuse(semantic: float, lexical: float, mode: str) -> float:
    if mode == "lexical":
        return lexical
    if mode == "semantic":
        return semantic
    return SEMANTIC_WEIGHT * semantic + LEXICAL_WEIGHT * lexical


def hybrid_search(
    query: str,
    chunks: list[Chunk],
    embed_fn: EmbedFn | None = None,
    mode: str = "hybrid",
) -> list[ScoredChunk]:
    """Score all chunks, keep top-8, rerank-stub (identity) to top-4."""
    if not chunks:
        return []
    embed = embed_fn or stub_embed
    qvec = list(embed(query))
    qtoks = word_tokens(query)
    doc_toks = [word_tokens(c.text) for c in chunks]
    idf = _idf_weights(doc_toks)
    scored = [
        ScoredChunk(
            chunk=c,
            semantic=cosine(qvec, list(embed(c.text))),
            lexical=lexical_score(qtoks, toks, idf),
            score=0.0,
        )
        for c, toks in zip(chunks, doc_toks)
    ]
    for item in scored:
        item.score = _fuse(item.semantic, item.lexical, mode)
    scored.sort(key=lambda item: item.score, reverse=True)
    retrieved = scored[:RETRIEVE_TOPK]
    # Rerank stub: identity (heuristic reranker OFF per CiteGuard 2.6).
    # Production slot: bge-reranker-v2-m3 cross-encoder, eval-gated.
    return retrieved[:RERANK_TOPK]


def retrieval_confidence(results: list[ScoredChunk]) -> float:
    """Top-1 hybrid score (0.0 when nothing retrieved)."""
    return max((item.score for item in results), default=0.0)


_DOC_REGISTRY: dict[str, list[str]] = {}


def register_doc(doc_id: str, pages: list[str]) -> None:
    """In-memory doc pages for tests/dev (Wave 3 wires the engine)."""
    _DOC_REGISTRY[doc_id] = list(pages)


def get_doc_pages(doc_id: str) -> list[str]:
    try:
        return _DOC_REGISTRY[doc_id]
    except KeyError:
        raise KeyError(f"doc_id {doc_id!r} not registered; send text for now") from None
