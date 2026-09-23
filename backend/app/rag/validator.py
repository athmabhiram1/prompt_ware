"""W2.3 sentence validator — Overlap>=0.10 OR Sim>=0.40 (CiteGuard 2.9 verbatim).

Disjoint critic: pure token math, no LLM. A claim is Supported when EITHER
word-overlap recall against the cited chunk reaches 0.10 OR token-cosine
similarity reaches 0.40. Per LegalHalluLens, refusals carry TYPED counters
(obligation / numeric / temporal) instead of a single hallucination %.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

OVERLAP_MIN = 0.10
SIM_MIN = 0.40

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NUM_RE = re.compile(r"\d")
_OBLIGATION_RE = re.compile(
    r"\b(shall|must|pay|rent|fee|due|notice|evict\w*|terminat\w*|liab\w*|arbitrat\w*)\b"
)
_TEMPORAL_RE = re.compile(
    r"\b(day\w*|month\w*|year\w*|week\w*|notice|before|after|deadline|within|\d{1,2}(st|nd|rd|th))\b"
)


def word_tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def token_overlap(claim: str, evidence: str) -> float:
    """|claim ∩ evidence| / |claim| — recall of claim terms in the chunk."""
    need = word_tokens(claim)
    if not need:
        return 0.0
    have = set(word_tokens(evidence))
    return sum(1 for t in need if t in have) / len(need)


def token_cosine(a: str, b: str) -> float:
    ca, cb = Counter(word_tokens(a)), Counter(word_tokens(b))
    if not ca or not cb:
        return 0.0
    dot = sum(ca[k] * cb.get(k, 0) for k in ca)
    denom = math.sqrt(sum(v * v for v in ca.values()) * sum(v * v for v in cb.values()))
    return dot / denom if denom else 0.0


@dataclass
class ClaimVerdict:
    supported: bool
    overlap: float
    sim: float


def validate_sentence(sentence: str, chunk_text: str) -> ClaimVerdict:
    overlap = token_overlap(sentence, chunk_text)
    sim = token_cosine(sentence, chunk_text)
    return ClaimVerdict(
        supported=(overlap >= OVERLAP_MIN or sim >= SIM_MIN),
        overlap=overlap,
        sim=sim,
    )


def classify_claim(text: str) -> dict[str, bool]:
    """Typed counters per claim (LegalHalluLens: never a single % metric)."""
    lowered = text.lower()
    return {
        "obligation": bool(_OBLIGATION_RE.search(lowered)),
        "numeric": bool(_NUM_RE.search(text)),
        "temporal": bool(_TEMPORAL_RE.search(lowered)),
    }
