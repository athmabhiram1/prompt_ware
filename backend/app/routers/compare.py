"""POST /compare — deterministic semantic delta (no LLM at request time).

Alignment is ID-first (same rule_id paired); unpaired excerpts fall back to
token-cosine: >0.85 same, 0.65-0.85 LLM-judge (deterministic stub returning
"clarified" — production swaps a real judge), <0.65 added/deleted.
NEW router only — wiring (`app.include_router(router)`) lands in Wave 3.
"""

import math
import re
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.limits import RATE_30_PER_MIN, limiter

from app.engine import contradict, playbook, redline
from app.engine.redline import RedlinesJson
from app.engine.rules import Finding, premise_kind, scan

router = APIRouter(tags=["compare"])

SAME_AT = 0.85
JUDGE_LO = 0.65

Label = Literal["cosmetic", "clarified", "risk-up", "risk-down", "moved", "deleted", "added", "same"]
Risk = Literal["green", "amber", "red"]
Side = Literal["v1", "v2"]


class Cite(BaseModel):
    rule_id: str
    excerpt: str
    start: int
    end: int
    side: Side


class Delta(BaseModel):
    label: Label
    risk: Risk
    party_impact: Literal["tenant", "landlord", "both"]
    one_liner: str
    cites: list[Cite] = Field(default_factory=list)


class Coverage(BaseModel):
    v1: float
    v2: float


class CompareRequest(BaseModel):
    a: str = Field(min_length=1, max_length=50000)
    b: str = Field(min_length=1, max_length=50000)
    premise: str = "residential"


class CompareResponse(BaseModel):
    deltas: list[Delta]
    coverage: Coverage
    removed_protections: list[str]
    verdict: playbook.Verdict


def _tokens(t: str) -> Counter[str]:
    return Counter(re.findall(r"[a-z0-9]+", t.lower()))


def token_cosine(a: str, b: str) -> float:
    ca, cb = _tokens(a), _tokens(b)
    if not ca or not cb:
        return 0.0
    dot = sum(ca[k] * cb.get(k, 0) for k in ca)
    return dot / math.sqrt(sum(v * v for v in ca.values()) * sum(v * v for v in cb.values()))


def llm_judge(a: str, b: str) -> Literal["clarified"]:
    """Deterministic stub for the 0.65-0.85 band; production swaps a real judge."""
    _ = (a, b)
    return "clarified"


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def _who(text: str) -> Literal["tenant", "landlord", "both"]:
    t = text.lower()
    if re.search(r"\btenant\b|\buser\b|\bcustomer\b", t):
        return "tenant"
    if re.search(r"\blandlord\b|\bcompany\b|\bowner\b", t):
        return "landlord"
    return "both"


def _cite_of(f: Finding, side: Side) -> Cite:
    return Cite(rule_id=f.rule_id, excerpt=f.excerpt, start=f.start, end=f.end, side=side)


def _risk_for_tier(tier: int) -> Risk:
    return "red" if tier >= 4 else ("amber" if tier == 3 else "green")


def _present(f: Finding) -> bool:
    return f.status != "missing" and bool(f.excerpt)


def _numeric_line(rid: str, fa: Finding, fb: Finding) -> str | None:
    for key in ("months", "amount", "notice_months"):
        va, vb = fa.data.get(key), fb.data.get(key)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and va != vb:
            arrow = "↑" if vb > va else "↓"
            return f"{rid} {key} {va} → {vb} {arrow}"
    return None


def _pair_deltas(fa: Finding, fb: Finding, full_a: str, full_b: str) -> list[Delta]:
    pa, pb = _present(fa), _present(fb)
    if not pa and not pb:
        return []
    if pa and not pb:
        if _norm(fa.excerpt) in _norm(full_b):
            return [Delta(label="moved", risk="green", party_impact="both",
                          one_liner=f"{fa.rule_id} moved within v2", cites=[_cite_of(fa, "v1")])]
        risk: Risk = "red" if fb.status == "missing" else "amber"
        return [Delta(label="deleted", risk=risk, party_impact=_who(fa.excerpt),
                      one_liner=f"{fa.rule_id} removed in v2 — {fa.clause}", cites=[_cite_of(fa, "v1")])]
    if pb and not pa:
        if _norm(fb.excerpt) in _norm(full_a):
            return [Delta(label="moved", risk="green", party_impact="both",
                          one_liner=f"{fb.rule_id} moved within v2", cites=[_cite_of(fb, "v2")])]
        return [Delta(label="added", risk=_risk_for_tier(fb.tier), party_impact=_who(fb.excerpt),
                      one_liner=f"{fb.rule_id} added in v2 — {fb.clause}", cites=[_cite_of(fb, "v2")])]
    if fa.excerpt == fb.excerpt:
        return []
    if _norm(fa.excerpt) == _norm(fb.excerpt):
        return [Delta(label="cosmetic", risk="green", party_impact="both",
                      one_liner=f"{fa.rule_id} wording polish only", cites=[_cite_of(fa, "v1"), _cite_of(fb, "v2")])]
    cites = [_cite_of(fa, "v1"), _cite_of(fb, "v2")]
    who = _who(fa.excerpt + " " + fb.excerpt)
    num = _numeric_line(fa.rule_id, fa, fb)
    if num and "↑" in num:
        return [Delta(label="risk-up", risk="red", party_impact=who,
                      one_liner=f"{num} — burden increased", cites=cites)]
    if fb.tier > fa.tier:
        return [Delta(label="risk-up", risk="red" if fb.tier >= 4 else "amber", party_impact=who,
                      one_liner=num or f"{fa.rule_id} tier {fa.tier} → {fb.tier} — risk increased", cites=cites)]
    if (num and "↓" in num) or fb.tier < fa.tier:
        return [Delta(label="risk-down", risk="green", party_impact=who,
                      one_liner=num or f"{fa.rule_id} tier {fa.tier} → {fb.tier} — risk eased", cites=cites)]
    sim = token_cosine(fa.excerpt, fb.excerpt)
    if sim >= SAME_AT:
        return [Delta(label="clarified", risk="green", party_impact=who,
                      one_liner=f"{fa.rule_id} reworded, substance same", cites=cites)]
    if sim >= JUDGE_LO:
        verdict = llm_judge(fa.excerpt, fb.excerpt)
        return [Delta(label=verdict, risk="green", party_impact=who,
                      one_liner=f"{fa.rule_id} judge: {verdict}", cites=cites)]
    return [Delta(label="deleted", risk="amber", party_impact=who,
                  one_liner=f"{fa.rule_id} replaced in v2", cites=[_cite_of(fa, "v1")]),
            Delta(label="added", risk=_risk_for_tier(fb.tier), party_impact=who,
                  one_liner=f"{fa.rule_id} replacement text in v2", cites=[_cite_of(fb, "v2")])]


def _sentences(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0).strip())
            for m in re.finditer(r"[^.!?]+[.!?]?", text) if m.group(0).strip()]


def _modal_deltas(a: str, b: str) -> list[Delta]:
    out: list[Delta] = []
    for sa_s, sa_e, sa in _sentences(a):
        _ = (sa_s, sa_e)
        if not re.search(r"\bshall\b", sa, re.IGNORECASE):
            continue
        best: tuple[float, int, int, str] = (0.0, 0, 0, "")
        for sb_s, sb_e, sb in _sentences(b):
            s = token_cosine(sa, sb)
            if s > best[0]:
                best = (s, sb_s, sb_e, sb)
        sim, bs, be, sb = best
        if sim >= JUDGE_LO and re.search(r"\bmust\b|\bmay\b|\bcan\b", sb, re.IGNORECASE) \
                and not re.search(r"\bshall\b", sb, re.IGNORECASE):
            hits = [f for f in scan(sb) if f.excerpt]
            rid = hits[0].rule_id if hits else "R07"
            out.append(Delta(label="risk-up", risk="red", party_impact=_who(sb),
                             one_liner=f"obligation weakened: 'shall' → 'may' in v2 — {sb[:80]}",
                             cites=[Cite(rule_id=rid, excerpt=sb, start=bs, end=be, side="v2")]))
    return out


def compare_texts(a: str, b: str, premise: str = "residential") -> CompareResponse:
    kind = premise_kind(premise)
    fa, fb = scan(a, kind), scan(b, kind)
    deltas: list[Delta] = []
    for ra, rb in zip(fa, fb):
        deltas.extend(_pair_deltas(ra, rb, a, b))
    seen_c = {(c.cid, c.excerpt) for c in contradict.detect(a, fa)}
    for c in contradict.detect(b, fb):
        if (c.cid, c.excerpt) not in seen_c:
            deltas.append(Delta(label="risk-up", risk="red", party_impact="both",
                                one_liner=f"new {c.cid}: {c.note}",
                                cites=[Cite(rule_id=c.cid, excerpt=c.excerpt,
                                            start=c.start, end=c.end, side="v2")]))
    deltas.extend(_modal_deltas(a, b))

    def _cov(fs: list[Finding]) -> float:
        return round(sum(1 for f in fs if _present(f)) / len(fs), 3)

    return CompareResponse(deltas=deltas, coverage=Coverage(v1=_cov(fa), v2=_cov(fb)),
                           removed_protections=playbook.removed_protection(fa, fb),
                           verdict=playbook.verdict(fb))


@router.post("/compare", response_model=CompareResponse)
@limiter.limit(RATE_30_PER_MIN)
def post_compare(request: Request, req: CompareRequest) -> CompareResponse:
    try:
        return compare_texts(req.a, req.b, req.premise)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=f"invalid compare input: {exc}") from exc


@router.post("/compare/redline", response_model=RedlinesJson)
@limiter.limit(RATE_30_PER_MIN)
def post_redline(request: Request, req: CompareRequest) -> RedlinesJson:
    try:
        res = compare_texts(req.a, req.b, req.premise)
        return redline.to_redlines_json([d.model_dump() for d in res.deltas])
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=f"invalid redline input: {exc}") from exc


@router.post("/compare/export.docx")
@limiter.limit(RATE_30_PER_MIN)
def post_redline_docx(request: Request, req: CompareRequest) -> Response:
    try:
        res = compare_texts(req.a, req.b, req.premise)
        blob = redline.build_redline_docx(redline.to_redlines_json([d.model_dump() for d in res.deltas]))
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=f"invalid export input: {exc}") from exc
    return Response(content=blob, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": "attachment; filename=redline.docx"})
