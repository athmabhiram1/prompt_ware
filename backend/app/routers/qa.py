"""W2.3 POST /qa — CiteGuard grounded Q&A with explicit abstention.

Contract (frozen for W3.1 brief; mirrored in ``frontend/src/lib/qa.ts``)::

    POST /qa {question, doc_id | job_id, mode="hybrid"}
      -> {answer | None, citations[{page, span, start, end}],
          abstain{reason, code} | None, audit[...],
          retrieval_confidence, support_ratio, regens}

Abstention policy (explicit thresholds + reason codes):
- retrieval_confidence (top-1 hybrid) < 0.10, or nothing retrieved
  -> NO_EVIDENCE (true refusal).
- mean retrieved score < 0.05 -> IRRELEVANT_EVIDENCE (true refusal).
- support_ratio (supported claims / all claims) < 1.0 after ONE regen
  -> UNSUPPORTED_AFTER_REGEN (false refusal; evidence existed but unusable).
- Refusal text is always the fixed template (never an invented answer).

NEW router only — wiring (``app.include_router(router)``) lands in Wave 3;
``main.py`` and the ``/query`` shape are untouched (AGENTS.md contract).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from app.core.limits import RATE_30_PER_MIN, limiter

from app.rag import llm as llm_mod
from app.rag import prompts, validator
from app.rag.chunk import Chunk, chunk_pages
from app.rag.llm import LlmFn
from app.rag.vec_mem import (
    ScoredChunk,
    get_doc_pages,
    hybrid_search,
    retrieval_confidence,
)

RETRIEVAL_MIN = 0.10
RELEVANCE_MIN = 0.05
SUPPORT_MIN = 1.0
MAX_REGENS = 1

Verdict = Literal["Supported", "Unsupported"]


class QaRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    doc_id: str | None = None
    job_id: str | None = None
    mode: Literal["hybrid", "lexical", "semantic"] = "hybrid"

    @model_validator(mode="after")
    def _need_target(self) -> QaRequest:
        if not (self.doc_id or self.job_id):
            raise ValueError("provide doc_id or job_id")
        return self


class QaCitation(BaseModel):
    page: int
    span: str
    start: int
    end: int


class QaAbstain(BaseModel):
    reason: str
    code: str


class AuditRow(BaseModel):
    sentence: str
    doc_id: str
    page: int
    start: int
    end: int
    verdict: Verdict
    overlap: float
    sim: float


class QaResponse(BaseModel):
    answer: str | None = None
    citations: list[QaCitation] = Field(default_factory=list)
    abstain: QaAbstain | None = None
    audit: list[AuditRow] = Field(default_factory=list)
    retrieval_confidence: float = 0.0
    support_ratio: float = 0.0
    regens: int = 0


def _abstain(
    code: str,
    kind: Literal["true", "false"],
    conf: float,
    claims: list[str],
    audit: list[AuditRow] | None = None,
    regens: int = 0,
) -> QaResponse:
    llm_mod.log_refusal(kind, code, claims)
    return QaResponse(
        answer=None,
        citations=[],
        abstain=QaAbstain(reason=prompts.refuse(code), code=code),
        audit=audit or [],
        retrieval_confidence=conf,
        support_ratio=0.0,
        regens=regens,
    )


def _validate_attempt(
    claims: list[prompts.ParsedClaim], by_id: dict[str, ScoredChunk]
) -> tuple[list[AuditRow], int]:
    rows: list[AuditRow] = []
    supported = 0
    for claim in claims:
        scored = by_id.get(claim.cite_ids[0]) if claim.cite_ids else None
        chunk: Chunk | None = scored.chunk if scored else None
        if chunk is None:
            verdict = validator.ClaimVerdict(supported=False, overlap=0.0, sim=0.0)
        else:
            verdict = validator.validate_sentence(claim.text, chunk.text)
        supported += 1 if verdict.supported else 0
        rows.append(
            AuditRow(
                sentence=claim.text,
                doc_id=chunk.doc_id if chunk else "",
                page=chunk.page if chunk else 0,
                start=chunk.start if chunk else 0,
                end=chunk.end if chunk else 0,
                verdict="Supported" if verdict.supported else "Unsupported",
                overlap=round(verdict.overlap, 4),
                sim=round(verdict.sim, 4),
            )
        )
    return rows, supported


def answer_question(
    question: str,
    retrieved: list[ScoredChunk],
    llm_fn: LlmFn,
    doc_id: str = "",
) -> QaResponse:
    """Grounded answer loop: draft -> protocol+validator -> ONE regen -> refuse."""
    conf = retrieval_confidence(retrieved)
    if not retrieved or conf < RETRIEVAL_MIN:
        return _abstain("NO_EVIDENCE", "true", conf, [])
    relevance = sum(item.score for item in retrieved) / len(retrieved)
    if relevance < RELEVANCE_MIN:
        return _abstain("IRRELEVANT_EVIDENCE", "true", conf, [])

    by_id = {item.chunk.chunk_id: item for item in retrieved}
    regens = 0
    rows: list[AuditRow] = []
    ratio = 0.0
    while True:
        draft = llm_fn(llm_mod.build_prompt(question, retrieved, strict=regens > 0))
        if draft.strip() == "NO_EVIDENCE":
            return _abstain("NO_EVIDENCE", "true", conf, [], regens=regens)
        claims = prompts.split_claims(draft)
        rows, supported = _validate_attempt(claims, by_id)
        ratio = supported / len(claims) if claims else 0.0
        if ratio >= SUPPORT_MIN:
            seen: list[QaCitation] = []
            used: set[str] = set()
            for claim in claims:
                cid = claim.cite_ids[0]
                if cid in used:
                    continue
                used.add(cid)
                chunk = by_id[cid].chunk
                seen.append(
                    QaCitation(
                        page=chunk.page,
                        span=chunk.text,
                        start=chunk.start,
                        end=chunk.end,
                    )
                )
            return QaResponse(
                answer=" ".join(claim.text for claim in claims),
                citations=seen,
                abstain=None,
                audit=rows,
                retrieval_confidence=round(conf, 4),
                support_ratio=ratio,
                regens=regens,
            )
        if regens >= MAX_REGENS:
            return _abstain(
                "UNSUPPORTED_AFTER_REGEN",
                "false",
                conf,
                [claim.text for claim in claims],
                audit=rows,
                regens=regens,
            )
        regens += 1


router = APIRouter(tags=["qa"])


@router.post("/qa", response_model=QaResponse)
@limiter.limit(RATE_30_PER_MIN)
def ask_qa(request: Request, payload: QaRequest) -> QaResponse:
    """Answer from a registered doc (pg-first store; stub path at LLM_LIVE=0)."""
    target = (payload.doc_id or payload.job_id or "").strip()
    try:
        pages = get_doc_pages(target)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"doc_id {target!r} not in registry; send text for now (Wave 3 wires engine).",
        ) from exc
    chunks = chunk_pages(target, pages)
    results = hybrid_search(payload.question, chunks, mode=payload.mode)
    return answer_question(
        payload.question,
        results,
        llm_fn=lambda prompt: llm_mod.draft_answer(payload.question, results),
        doc_id=target,
    )
