"""C1-C4 contradiction detectors (regex only, no LLM).

C1 amount-mismatch: two different deposit/consideration amounts in one doc.
C2 understates-statute: clause grants less than statute (non-refundable
    deposit, refund slower than 1 month, overstay below 2x/4x).
C3 short-revision: rent-revision notice below 3 months.
C4 outdated-tds: 5% TDS rate cited (current 2% since 1-Oct-2024).
"""

import re

from pydantic import BaseModel

from app.engine.rules import (
    FLAGS,
    Finding,
    _AMOUNT_RE,
    parse_months,
    window_for,
)


class Contradiction(BaseModel):
    """Frozen schema: cited by W3.1 brief alongside Finding."""

    cid: str
    excerpt: str
    start: int
    end: int
    note: str = ""


def _cite(cid: str, text: str, m: re.Match[str], note: str) -> Contradiction:
    s, e = window_for(text, m.start(), m.end())
    return Contradiction(cid=cid, excerpt=text[s:e], start=s, end=e, note=note)


def _c1(text: str) -> list[Contradiction]:
    seen: list[tuple[float, re.Match[str]]] = []
    for m in re.finditer(_AMOUNT_RE, text, FLAGS):
        try:
            amt = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if amt >= 1000:
            seen.append((amt, m))
    vals = {a for a, _ in seen}
    if len(vals) >= 2:
        _, m = seen[-1]
        return [_cite("C1", text, m, f"amount mismatch in one document: {sorted(vals)}")]
    words = re.findall(r"\(([^)]*(?:month|rupee|lakh)[^)]*)\)", text, FLAGS)
    if len({w.strip().lower() for w in words}) >= 2:
        m = re.search(r"\([^)]*\)", text, FLAGS)
        assert m is not None
        return [_cite("C1", text, m, f"figures-vs-words mismatch: {words}")]
    return []


def _c2(text: str) -> list[Contradiction]:
    out: list[Contradiction] = []
    m = re.search(r"security\s*deposit.{0,80}non[-\s]?refundable|non[-\s]?refundable.{0,80}deposit", text, FLAGS)
    if m:
        out.append(_cite("C2", text, m, "non-refundable deposit understates Sec-11 refund right"))
    m = re.search(r"refund\w*.{0,80}(?:two|three|2|3)\s*months?", text, FLAGS)
    if m:
        out.append(_cite("C2", text, m, "refund slower than 1-month statutory timeline"))
    m = re.search(r"overstay.{0,80}(?:1\.5|one\s+and\s+a\s+half)\s*(?:times|x)", text, FLAGS)
    if m:
        out.append(_cite("C2", text, m, "overstay below statutory 2x/4x multipliers"))
    return out


def _c3(text: str, findings: list[Finding]) -> list[Contradiction]:
    for f in findings:
        if f.rule_id == "R05" and f.status == "hit" and f.data.get("notice_months") is not None:
            m = re.search(r"revise|revision|increase\s+(?:of\s+)?rent", text, FLAGS)
            if m:
                return [_cite("C3", text, m, f"revision notice {f.data['notice_months']}mo < 3mo")]
    m = re.search(r"(?:notice\s+of\s+)?(?:(\d+)\s*days?|one\s+month).{0,40}(?:revis|increas).{0,20}rent", text, FLAGS)
    if m:
        months = parse_months(m.group(0))
        days = int(m.group(1)) if m.group(1) else 30
        if (months is not None and months < 3) or (months is None and days < 90):
            return [_cite("C3", text, m, "revision notice below 3 months")]
    return []


def _c4(text: str) -> list[Contradiction]:
    m = re.search(r"(?:tds|194[-\s]?i\s?b).{0,40}5\s*%|5\s*%.{0,40}(?:tds|194[-\s]?i\s?b)", text, FLAGS)
    if m:
        return [_cite("C4", text, m, "outdated 5% TDS — current 2% since 1-Oct-2024")]
    return []


def detect(text: str, findings: list[Finding] | None = None) -> list[Contradiction]:
    """Detect C1-C4 in reading order. Excerpts are ≤800-char windows."""
    found = findings if findings is not None else []
    out = _c1(text) + _c2(text) + _c3(text, found) + _c4(text)
    return sorted(out, key=lambda c: c.start)


CIDS = ["C1", "C2", "C3", "C4"]
