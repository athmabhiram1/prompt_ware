"""W2.3 LLM abstraction — stub default (LLM_LIVE=0), live hook for Wave 3.

Provider fallback order Gemini -> Groq -> Ollama lives in
``backend/llm_provider.py`` (untouched); this module only adapts prompts to
answers. ``LLM_LIVE=1`` without a configured provider falls back to the stub
and is NEVER exercised in tests (mocked vectors + canned chunks only).
True/False refusals are logged separately with typed claim counters.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Literal

from app.rag import prompts
from app.rag.vec_mem import ScoredChunk
from app.rag.validator import classify_claim

LlmFn = Callable[[str], str]

REFUSAL_LOG: list[dict] = []


def build_prompt(question: str, results: list[ScoredChunk], strict: bool = False) -> str:
    blocks = "\n".join(
        f"[{item.chunk.chunk_id} p.{item.chunk.page}] {item.chunk.text}" for item in results
    )
    note = f"\n{prompts.REGEN_STRICT_NOTE}" if strict else ""
    return f"{prompts.CREAC_SYSTEM}\nQUESTION: {question}\nEVIDENCE:\n{blocks}{note}"


def stub_answer(question: str, results: list[ScoredChunk]) -> str:
    """Extractive stub: first sentence of the top chunk + true cite."""
    from app.rag.chunk import split_sentences

    if not results:
        return "NO_EVIDENCE"
    top = results[0].chunk
    sents = split_sentences(top.text)
    first = sents[0] if sents else top.text
    _ = question
    return f"{first} {{cite:{top.chunk_id}}}"


def draft_answer(question: str, results: list[ScoredChunk], strict: bool = False) -> str:
    """Live hook: stub unless LLM_LIVE=1 (Wave 3 fills the live branch)."""
    _ = strict
    if os.getenv("LLM_LIVE", "0") == "1":
        # Wave 3: route build_prompt() through llm_provider.get_llm_func().
        return stub_answer(question, results)
    return stub_answer(question, results)


def log_refusal(
    kind: Literal["true", "false"],
    code: str,
    claim_texts: list[str],
) -> dict:
    """True refusal = correctly abstained (no evidence); false = abstained
    despite retrieved evidence (regen exhausted). Typed counters attached."""
    counters = {"obligation": 0, "numeric": 0, "temporal": 0}
    for text in claim_texts:
        for key, hit in classify_claim(text).items():
            counters[key] += 1 if hit else 0
    entry = {"kind": kind, "code": code, "claims": len(claim_texts), **counters}
    REFUSAL_LOG.append(entry)
    return entry
