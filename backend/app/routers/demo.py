"""W4.1 GET /demo/* — frozen offline bundles, cache-only, zero live calls.

Serves ``data/preindex/{msa,nda,offer}.json`` built deterministically by
``scripts/build_demo_bundles.py`` (W2 engine outputs only: scan R01-R18,
maths M1/M3, contradict C1-C4, simplify, brief). This module imports no
LLM/graph/network SDKs — not even indirectly — so it stays fast when Aura
is paused, Render is cold, or ``LLM_LIVE=0``. ``LLM_LIVE=1`` still serves
cache: /demo/* never dials out by construction.

Route map: ``priya -> msa.json`` (Bengaluru lease), ``msme -> nda.json``,
``dpdp -> offer.json``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/demo", tags=["demo"])

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_DIR = _BACKEND_DIR.parent

BUNDLE_DIR = _REPO_DIR / "data" / "preindex"

DEMO_TO_BUNDLE: dict[str, str] = {
    "priya": "msa.json",
    "msme": "nda.json",
    "dpdp": "offer.json",
}

# Flat JSON scalar/container alias: true recursion would need PEP 695 type
# aliases, so heterogeneous bundle subtrees get explicit block models below.
JsonValue = str | int | float | bool | None | list | dict


class DemoMeta(BaseModel):
    served_from: str = "cache"
    llm_live: bool = False


class BundleDoc(BaseModel):
    """One frozen source doc (bundle ``docs`` entries)."""

    model_config = ConfigDict(extra="allow")

    doc_id: str = ""
    name: str = ""
    text: str = ""


class AuditFinding(BaseModel):
    """One R01-R18 finding (``risks`` + ``missing`` share this shape)."""

    model_config = ConfigDict(extra="allow")

    rule_id: str = ""
    clause: str = ""
    excerpt: str = ""
    start: int = 0
    end: int = 0
    status: str = ""
    tier: int = 0
    note: str = ""
    data: dict[str, JsonValue] = Field(default_factory=dict)


class AuditObligation(BaseModel):
    """One computed statutory obligation."""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    statute: str = ""
    duty: str = ""
    computed: str = ""
    deadline: str = ""
    source_rule: str = ""


class AuditContradiction(BaseModel):
    """One C1-C4 cross-clause contradiction."""

    model_config = ConfigDict(extra="allow")

    cid: str = ""
    excerpt: str = ""
    start: int = 0
    end: int = 0
    note: str = ""


class AuditBlock(BaseModel):
    """Frozen W2 engine audit (risks + missing + obligations + contradicts)."""

    model_config = ConfigDict(extra="allow")

    risks: list[AuditFinding] = Field(default_factory=list)
    missing: list[AuditFinding] = Field(default_factory=list)
    obligations: list[AuditObligation] = Field(default_factory=list)
    contradictions: list[AuditContradiction] = Field(default_factory=list)
    rule_count: int = 0


class SimplifyCite(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int = 0
    start: int = 0
    end: int = 0


class SimplifySentenceBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str = ""
    cite: SimplifyCite = Field(default_factory=SimplifyCite)


class SimplifyScores(BaseModel):
    model_config = ConfigDict(extra="allow")

    fk: float = 0.0
    fre: float = 0.0


class SimplifyGlossaryTerm(BaseModel):
    model_config = ConfigDict(extra="allow")

    term: str = ""
    definition: str = ""
    hi: str = ""


class SimplifyBlock(BaseModel):
    """Frozen W2.1 simplify output (mirrors ``simplify.py`` response shape)."""

    model_config = ConfigDict(extra="allow")

    sentences: list[SimplifySentenceBlock] = Field(default_factory=list)
    before: SimplifyScores = Field(default_factory=SimplifyScores)
    after: SimplifyScores = Field(default_factory=SimplifyScores)
    glossary: list[SimplifyGlossaryTerm] = Field(default_factory=list)
    level: str = "8"
    lang: str = "en"


class QaCitation(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int = 0
    span: str = ""
    start: int = 0
    end: int = 0


class QaAbstain(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str = ""
    reason: str = ""


class QaBlock(BaseModel):
    """One frozen Q&A pair (answer XOR abstain carries the payload)."""

    model_config = ConfigDict(extra="allow")

    question: str = ""
    answer: str | None = None
    citations: list[QaCitation] = Field(default_factory=list)
    abstain: QaAbstain | None = None


class BriefTrailRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = ""
    section: str = ""
    timestamp: str = ""


class BriefCite(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int = 0
    start: int = 0
    end: int = 0
    excerpt: str = ""
    rule_id: str = ""


class BriefBlock(BaseModel):
    """Frozen W3.1 brief output."""

    model_config = ConfigDict(extra="allow")

    markdown: str = ""
    redline_docx_path: str = ""
    questions_for_lawyer: list[str] = Field(default_factory=list)
    verification_trail: list[BriefTrailRow] = Field(default_factory=list)
    cites: list[BriefCite] = Field(default_factory=list)
    disclaimer: str = ""


class DemoResponse(BaseModel):
    demo_id: str
    bundle: str = ""
    doc_id: str = ""
    title: str = ""
    story: str = ""
    premise: str = ""
    pincode: str = ""
    text: str
    docs: list[BundleDoc] = Field(default_factory=list)
    audit: AuditBlock
    simplify: SimplifyBlock = Field(default_factory=SimplifyBlock)
    qa: list[QaBlock] = Field(default_factory=list)
    brief: BriefBlock = Field(default_factory=BriefBlock)
    meta: DemoMeta = Field(default_factory=DemoMeta)


@lru_cache(maxsize=4)
def load_bundle(demo_id: str) -> dict[str, JsonValue]:
    """Read a frozen bundle from disk (cached in-process; no I/O per hit)."""
    key = demo_id.strip().lower()
    if key not in DEMO_TO_BUNDLE:
        raise HTTPException(
            status_code=404,
            detail=f"unknown demo {demo_id!r}; try one of {sorted(DEMO_TO_BUNDLE)}",
        )
    path = BUNDLE_DIR / DEMO_TO_BUNDLE[key]
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"bundle {path.name} not built; run scripts/build_demo_bundles.py",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=500, detail=f"bundle {path.name} unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict) or not payload.get("text"):
        raise HTTPException(
            status_code=500, detail=f"bundle {path.name} has no demo text"
        )
    return payload


@router.get("/{demo_id}", response_model=DemoResponse)
def get_demo(demo_id: str) -> DemoResponse:
    """Serve a frozen demo audit (cache-only; ignores LLM_LIVE by design)."""
    payload = dict(load_bundle(demo_id))
    # Cache always wins: LLM_LIVE is ignored by design (never dials out),
    # so report llm_live False — this endpoint never makes a live call.
    payload["meta"] = {"served_from": "cache", "llm_live": False}
    return DemoResponse(**payload)


@router.get("", response_model=list[str])
def list_demos() -> list[str]:
    """List available frozen demo ids."""
    return sorted(DEMO_TO_BUNDLE)
