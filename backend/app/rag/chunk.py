"""W2.3 CiteGuard chunker — 600 tokens / 120 overlap, page-span constrained.

CiteGuard RAG section 2.3 numbers, verbatim: windows of at most 600 tokens
with 120-token overlap. A chunk NEVER spans pages: every chunk carries one
``page`` and char offsets ``[start, end)`` into that page's text, so
``page_text[start:end] == chunk.text`` always holds and citations cannot
leak across page boundaries. Token estimate is whitespace-based (matches
test/validator accounting; production Gemini counting recalibrates it).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHUNK_TOKENS = 600
CHUNK_OVERLAP_TOKENS = 120

_SENT_RE = re.compile(r"[^.!?\n]+[.!?]+|[^.!?\n]+$")


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    chunk_id: str
    page: int  # 1-based page number
    start: int  # char offset into the page text (inclusive)
    end: int  # char offset into the page text (exclusive)
    text: str


def estimate_tokens(text: str) -> int:
    """Whitespace token estimate (deterministic, no model call)."""
    return len(text.split())


def split_sentences(text: str) -> list[str]:
    """Split on sentence terminals; keeps delimiters, drops blanks."""
    return [m.group(0).strip() for m in _SENT_RE.finditer(text) if m.group(0).strip()]


def _sentence_spans(page: str) -> list[tuple[int, int]]:
    """Locate each sentence span in the ORIGINAL page (offsets stay exact)."""
    spans: list[tuple[int, int]] = []
    cursor = 0
    for sent in split_sentences(page):
        idx = page.find(sent, cursor)
        if idx < 0:
            continue
        spans.append((idx, idx + len(sent)))
        cursor = idx + len(sent)
    return spans


def chunk_pages(doc_id: str, pages: list[str]) -> list[Chunk]:
    """Sliding sentence windows per page (<=600 tok, ~120 tok overlap)."""
    chunks: list[Chunk] = []
    for page_no, page in enumerate(pages, start=1):
        spans = _sentence_spans(page)
        if not spans:
            continue
        seq = 0
        idx = 0
        while idx < len(spans):
            end = idx
            used = 0
            while end < len(spans):
                cost = estimate_tokens(page[spans[end][0] : spans[end][1]])
                if used and used + cost > CHUNK_TOKENS:
                    break
                used += cost
                end += 1
            if end == idx:  # single oversize sentence: keep whole, never split
                end = idx + 1
            start, stop = spans[idx][0], spans[end - 1][1]
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}:p{page_no}:{seq}",
                    page=page_no,
                    start=start,
                    end=stop,
                    text=page[start:stop],
                )
            )
            seq += 1
            if end >= len(spans):
                break
            back, acc = end - 1, 0  # step back to ~120 overlap tokens
            while back > idx:
                acc += estimate_tokens(page[spans[back][0] : spans[back][1]])
                if acc >= CHUNK_OVERLAP_TOKENS:
                    break
                back -= 1
            idx = back if back > idx else idx + 1
    return chunks
