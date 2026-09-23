"""W2.3 CREAC answer prompt + cite protocol + refuse template.

Every generated claim sentence MUST end with a ``{cite:chunk_id}`` marker
(GANDR-inspired ``protocol_check``: an answer with an uncited claim is
rejected before validation). The disjoint-critic note: a second,
non-generating pass (the validator) judges support — the generator never
grades its own output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CREAC_SYSTEM = """You answer ONLY from the EVIDENCE chunks below (CREACgrounded Q&A).
Structure: Conclusion, Rule, Evidence, Application, Conclusion.
Rules:
- Every claim sentence MUST end with exactly one {cite:chunk_id} marker
  referencing the chunk that states it (e.g. {cite:lease1:p1:0}).
- Copy numbers, dates and names EXACTLY as written in the chunk.
- If no chunk supports the question, output exactly: NO_EVIDENCE.
- Never invent a chunk_id. Never cite from memory."""

REFUSE_TEMPLATE = (
    "The document does not contain sufficient information "
    "to answer this question. [{code}]"
)

REGEN_STRICT_NOTE = (
    "STRICT REGEN: your previous draft cited missing or unsupported spans. "
    "Rewrite using ONLY attached chunk_ids, one true {cite:id} per sentence, "
    "or output exactly NO_EVIDENCE."
)

CITE_RE = re.compile(r"\{cite:([A-Za-z0-9_:.\-]+)\}")


@dataclass
class ParsedClaim:
    text: str
    cite_ids: list[str] = field(default_factory=list)


def split_claims(draft: str) -> list[ParsedClaim]:
    """Strip markers, split sentences, re-attach markers positionally."""
    from app.rag.chunk import split_sentences

    ids = CITE_RE.findall(draft)
    cleaned = CITE_RE.sub("", draft)
    sents = [s.strip() for s in split_sentences(cleaned) if s.strip()]
    claims = [
        ParsedClaim(text=s, cite_ids=[ids[i]] if i < len(ids) else [])
        for i, s in enumerate(sents)
    ]
    for extra in ids[len(sents) :]:
        claims.append(ParsedClaim(text="", cite_ids=[extra]))
    return claims


def protocol_errors(claims: list[ParsedClaim], known_ids: set[str]) -> list[str]:
    """GANDR protocol_check: every claim has exactly one KNOWN cite."""
    errors: list[str] = []
    for n, claim in enumerate(claims):
        if not claim.text:
            errors.append(f"claim {n}: empty text")
        if not claim.cite_ids:
            errors.append(f"claim {n}: missing {{cite:id}}")
        for cid in claim.cite_ids:
            if cid not in known_ids:
                errors.append(f"claim {n}: unknown cite id {cid!r}")
    return errors


def refuse(code: str) -> str:
    return REFUSE_TEMPLATE.format(code=code)
