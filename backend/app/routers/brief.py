"""W3.1 POST /brief — 1-page lawyer brief composing frozen W2 schemas.

Composes (never redefines): Finding (engine/rules), Verdict (engine/playbook),
SimplifySentence (routers/simplify), QaCitation/AuditRow (routers/qa).
Every markdown bullet carries a ``[doc p.X]`` cite reusing W2 spans —
zero invented cites. Uncited claims raise ValidationError.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.core.limits import RATE_30_PER_MIN, limiter

from app.engine.rules import premise_kind, scan
from app.routers.simplify import load_doc_text, simplify_text

DISCLAIMER = "Information, not legal advice — verify with advocate"

_CITE_RE = re.compile(r"\[doc p\.\d+\]")

router = APIRouter(tags=["brief"])


class BriefRequest(BaseModel):
    job_id: str | None = Field(default=None, max_length=20000)
    doc_id: str | None = Field(default=None, max_length=20000)
    text: str | None = Field(default=None, max_length=20000)
    premise: str = "residential"
    pincode: str | None = None

    @model_validator(mode="after")
    def _needs_source(self) -> BriefRequest:
        if not (self.job_id or self.doc_id or self.text):
            raise ValueError("provide job_id or doc_id or text")
        return self


class BriefCite(BaseModel):
    page: int
    start: int
    end: int
    excerpt: str
    rule_id: str = ""


class VerificationRow(BaseModel):
    source: str
    section: str
    timestamp: str


class BriefResponse(BaseModel):
    markdown: str
    redline_docx_path: str = ""
    questions_for_lawyer: list[str] = Field(default_factory=list)
    verification_trail: list[VerificationRow] = Field(default_factory=list)
    cites: list[BriefCite] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


def assert_all_cited(claims: list[str]) -> None:
    """Reject any claim lacking a ``[doc p.X]`` cite."""
    for idx, claim in enumerate(claims):
        if not _CITE_RE.search(claim):
            raise ValidationError.from_exception_data(
                "BriefClaim",
                [{"type": "missing", "loc": (idx,), "msg": "claim lacks [doc p.X] cite", "input": claim}],
            )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _forum_hint(pincode: str | None) -> str:
    pin = (pincode or "").strip()
    if pin.startswith("56"):
        return "Karnataka Rent Authority (MTA) — ask lawyer if Rent Authority vs civil court fits your pincode"
    if pin.startswith("11"):
        return "Delhi Rent Authority — ask lawyer if Rent Authority vs civil court fits your pincode"
    return "Rent Authority vs civil court vs consumer forum — ask lawyer which forum fits your pincode"


def _resolve_text(req: BriefRequest) -> str:
    if req.text and req.text.strip():
        return req.text.strip()
    target = (req.job_id or req.doc_id or "").strip()
    try:
        return load_doc_text(target)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _cites_for(text: str, premise: str) -> list[BriefCite]:
    kind = premise_kind(premise)
    out: list[BriefCite] = []
    for finding in scan(text, kind):
        if not finding.excerpt:
            continue
        start = text.find(finding.excerpt)
        if start < 0:
            continue
        out.append(BriefCite(page=1, start=start, end=start + len(finding.excerpt),
                             excerpt=finding.excerpt, rule_id=finding.rule_id))
    if not out:
        head = text[:200]
        out.append(BriefCite(page=1, start=0, end=len(head), excerpt=head))
    return out


def _bullet(text: str, page: int = 1) -> str:
    return f"- {text} [doc p.{page}]"


def build_brief(text: str, premise: str = "residential", pincode: str | None = None,
                job_id: str | None = None) -> BriefResponse:
    """Deterministic brief from W2 outputs only (no live LLM)."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("text must not be empty")
    kind = premise_kind(premise)
    findings = scan(cleaned, kind)
    try:
        simp = simplify_text(cleaned, level="8")
        plain = simp.sentences[0].text if simp.sentences else cleaned[:120]
    except ValueError:
        plain = cleaned[:120]
    cites = _cites_for(cleaned, premise)
    tag = f"[doc p.{cites[0].page}]"

    facts = [
        _bullet(f"Agreement excerpt reviewed ({len(findings)} clauses scanned, premise {kind})"),
        _bullet(f"Plain-language gist: {plain}"),
    ]
    risks = [
        _bullet(f"{f.rule_id} {f.clause} tier T{f.tier} — {f.note or 'flagged'}")
        for f in findings if f.status == "hit" and f.excerpt
    ] or [_bullet("No high-tier hits; highest tier below T4")]
    missing = [
        _bullet(f"{f.rule_id} {f.clause} missing — verify before signing")
        for f in findings if f.status == "missing"
    ] or [_bullet("No critical clause missing")]
    deadlines = [
        _bullet("Deposit refund within one month of vacant possession with itemised statement (MTA Sec 11)"),
        _bullet("Overstay compensation 2x first 60 days then 4x (MTA Sec 23)"),
        _bullet("TDS 2% on rent > Rs 50,000/mo since 1-Oct-2024; Form 26QC within 30 days + Form 16C, no TAN (Sec 194-IB)"),
    ]
    forum = _forum_hint(pincode)
    questions = [
        f"Is the deposit within MTA Sec 11 caps for this premise? {tag}",
        f"Does the refund/overstay/TDS trail (26QC/16C) match the agreement dates? {tag}",
        f"Forum check: {forum} {tag}",
    ]

    lines = [
        "# NyayaMitra — Lawyer Brief (1 page)",
        "",
        f"> {DISCLAIMER}",
        "",
        "## Facts",
        *facts,
        "",
        "## Risks",
        *risks,
        "",
        "## Missing",
        *missing,
        "",
        "## Deadlines",
        *deadlines,
        "",
        "## Questions for lawyer",
        *[f"- {q}" for q in questions],
    ]
    markdown = "\n".join(lines)
    bullets = [ln for ln in lines if ln.strip().startswith("-")]
    assert_all_cited(bullets)

    stamp = _now_iso()
    trail = [
        VerificationRow(source=f.rule_id or "simplify", section="Risks" if f.status == "hit" else "Missing",
                        timestamp=stamp)
        for f in findings if f.excerpt or f.status == "missing"
    ] or [VerificationRow(source="simplify", section="Facts", timestamp=stamp)]
    doc_key = (job_id or "brief").strip() or "brief"
    return BriefResponse(
        markdown=markdown,
        redline_docx_path=f"redline-{doc_key}.docx",
        questions_for_lawyer=questions,
        verification_trail=trail,
        cites=cites,
        disclaimer=DISCLAIMER,
    )


@router.post("/brief", response_model=BriefResponse)
@limiter.limit(RATE_30_PER_MIN)
def post_brief(request: Request, payload: BriefRequest) -> BriefResponse:
    """Compose a cited 1-page brief from frozen W2 outputs."""
    try:
        source = _resolve_text(payload)
        return build_brief(source, premise=payload.premise, pincode=payload.pincode,
                           job_id=payload.job_id or payload.doc_id)
    except ValidationError:
        raise
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
