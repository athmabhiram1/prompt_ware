"""W2.1 SIMPLIFY vertical — router + frozen schemas.

Contract (frozen for W3.1 brief; mirrored in ``frontend/src/lib/simplify.ts``)::

    POST /simplify {doc_id | text, level: 5|8|10|pro, lang: en|hi}
      -> {sentences, before: {fk, fre}, after: {fk, fre},
          glossary: [{term, def, hi}], level, lang}

Deterministic core (FK/FRE, grading, Hindi subs) lives in
``simplify_engine.py``; this module owns the Pydantic schemas, the
``simplify_text`` pipeline, ``doc_id`` resolution, and the route.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.limits import RATE_30_PER_MIN, limiter
from app.routers.simplify_engine import (  # re-exported for compat (tests/brief)
    FK_LEVEL_TARGETS,
    extract_glossary,
    flesch_kincaid,
    flesch_reading_ease,
    hindi_with_bracket,
    score,
    simplify_sentence,
    split_clauses,
    split_sentences,
    to_hindi_sentence,
)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_DIR = _BACKEND_DIR.parent
_PREINDEX_CANDIDATES: tuple[Path, ...] = (
    _REPO_DIR / "data" / "preindex",
    _BACKEND_DIR / "data" / "preindex",
)


class Cite(BaseModel):
    """Real chunk span: page is 1-based, [start, end) char offsets."""

    page: int
    start: int
    end: int

    @model_validator(mode="after")
    def _span_must_be_real(self) -> Cite:
        if self.page < 1 or self.start < 0 or self.end <= self.start:
            raise ValueError(f"invalid cite span: {self!r}")
        return self


class SimplifySentence(BaseModel):
    text: str
    cite: Cite


class ReadScores(BaseModel):
    fk: float
    fre: float


class GlossaryTerm(BaseModel):
    term: str
    definition: str
    hi: str = ""


class TextChunk(BaseModel):
    page: int
    text: str


class SimplifyRequest(BaseModel):
    doc_id: str | None = Field(default=None, max_length=2000)
    text: str | None = Field(default=None, max_length=50000)
    level: int | str = 8
    lang: str = "en"

    @field_validator("level")
    @classmethod
    def _normalize_level(cls, value: int | str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in FK_LEVEL_TARGETS:
            raise ValueError(f"level must be one of 5|8|10|pro, got {value!r}")
        return normalized

    @field_validator("lang")
    @classmethod
    def _normalize_lang(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"en", "hi"}:
            raise ValueError(f"lang must be en|hi, got {value!r}")
        return normalized

    @model_validator(mode="after")
    def _needs_source(self) -> SimplifyRequest:
        if not (self.doc_id or self.text):
            raise ValueError("provide doc_id or text")
        return self


class SimplifyResponse(BaseModel):
    sentences: list[SimplifySentence]
    before: ReadScores
    after: ReadScores
    glossary: list[GlossaryTerm]
    level: str
    lang: str


def simplify_text(text: str, level: str = "8", lang: str = "en") -> SimplifyResponse:
    """Deterministic pipeline: split -> grade (EN) -> translate (HI) -> cite."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("text must not be empty")
    chunks = split_clauses(cleaned)
    sentences: list[SimplifySentence] = []
    graded_all: list[str] = []
    for chunk in chunks:
        # Cites ground against the ORIGINAL chunk text; each graded part
        # reuses its source sentence span (never invented, may repeat).
        cursor = 0
        for source in split_sentences(chunk.text):
            start = chunk.text.find(source, cursor)
            if start < 0:
                raise ValueError(
                    f"ungrounded sentence in page {chunk.page}: {source[:60]!r}"
                )
            cursor = start + len(source)
            cite = Cite(page=chunk.page, start=start, end=cursor)
            for graded_text in simplify_sentence(source, level):
                final = to_hindi_sentence(graded_text) if lang == "hi" else graded_text
                sentences.append(SimplifySentence(text=final, cite=cite))
                graded_all.append(graded_text)
    after_text = " ".join(graded_all) if graded_all else cleaned
    return SimplifyResponse(
        sentences=sentences,
        before=score(cleaned),
        after=score(after_text),
        glossary=extract_glossary(cleaned),
        level=level,
        lang=lang,
    )


def load_doc_text(doc_id: str) -> str:
    """Resolve ``doc_id`` from committed preindex bundles (Wave 3: engine)."""
    needle = doc_id.strip().lower()
    for directory in _PREINDEX_CANDIDATES:
        try:
            if not directory.is_dir():
                continue
            for bundle in sorted(directory.glob("*.json")):
                try:
                    payload = json.loads(bundle.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                docs = payload if isinstance(payload, list) else payload.get("docs", [])
                for doc in docs:
                    if not isinstance(doc, dict):
                        continue
                    keys = {
                        str(doc.get(k, "")).lower() for k in ("doc_id", "id", "name")
                    }
                    if needle in keys and doc.get("text"):
                        return str(doc["text"])
        except OSError:
            continue
    raise HTTPException(
        status_code=404,
        detail=f"doc_id {doc_id!r} not in preindex bundles; send text for now (Wave 3 wires engine).",
    )


router = APIRouter(prefix="/simplify", tags=["simplify"])


@router.post("", response_model=SimplifyResponse)
@limiter.limit(RATE_30_PER_MIN)
def simplify(request: Request, payload: SimplifyRequest) -> SimplifyResponse:
    """Grade a doc (LLM-off deterministic core; LLM_LIVE hook lands Wave 3)."""
    _ = os.getenv("LLM_LIVE", "0")  # stub default respected; live fills defs later
    source = (
        payload.text.strip() if payload.text else load_doc_text(payload.doc_id or "")
    )
    try:
        return simplify_text(source, level=str(payload.level), lang=payload.lang)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
