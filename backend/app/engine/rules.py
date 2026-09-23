"""R01-R18 deterministic clause rules (regex only, no LLM, no network).

Encoding: `text` is a UTF-8-decoded Python str. All offsets are str
(codepoint) indices, so `original[start:end] == excerpt` always holds.
Every excerpt is a slice of a clause window of at most 800 chars.
All patterns run with `re.IGNORECASE | re.DOTALL`.
Family matchers live in `rules_money` (R01-R05/R12/R18) and
`rules_safeguard` (R13/R15/R17); this module holds the table + dispatch.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

FLAGS = re.IGNORECASE | re.DOTALL
WINDOW = 800
LEAD = 200

Status = Literal["hit", "pass", "missing"]

_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
    "eighteen": 18, "thirty": 30, "thirty-six": 36, "thirtysix": 36,
}
_MONTHS_RE = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve|thirty[\s-]?six)\s*[-]?\s*months?"
_AMOUNT_RE = r"(?:rs\.?|inr|₹)\s*([\d,]+)"


class Finding(BaseModel):
    """Frozen schema: W3.1 brief cites these verbatim. Never rename fields."""

    rule_id: str
    clause: str
    excerpt: str
    start: int
    end: int
    status: Status
    tier: int = Field(ge=1, le=5)
    note: str = ""
    data: dict[str, str | float | bool] = Field(default_factory=dict)


@dataclass
class RuleSpec:
    rule_id: str
    clause: str
    tier_hit: int
    tier_pass: int
    required: bool
    hit: list[str] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)


RULES: list[RuleSpec] = [
    RuleSpec("R01", "deposit", 4, 1, True, [r"security\s*deposit|deposit\s*(?:of|amount|is)"]),
    RuleSpec("R02", "deposit", 4, 1, True, [r"security\s*deposit|deposit\s*(?:of|amount|is)"]),
    RuleSpec("R03", "deposit", 3, 1, False, [],
             [r"refund\w*\s+within\s+(?:one\s+month|1\s+month|30\s+days)"]),
    RuleSpec("R04", "overstay", 3, 2, False,
             [r"overstay|holdover|stay\s*over|remain\s+in\s+possession\s+after"],
             [r"twice\s+the\s+(?:monthly\s+)?rent.{0,80}four\s+times|2x.{0,40}4x"]),
    RuleSpec("R05", "rent_revision", 3, 2, False,
             [r"revise|revision|increase\s+(?:of\s+)?rent|rent\s+(?:may|shall)\s+be\s+(?:revised|increased)"]),
    RuleSpec("R06", "tenure", 3, 2, True,
             [r"lock[-\s]?in|initial\s+term|fixed\s+term"],
             [r"term\s+of\s+\d+|for\s+a\s+period\s+of|\d+\s*[-]?\s*(?:months?|years?)\s+(?:term|tenure|lease)|lease\s+for"]),
    RuleSpec("R07", "maintenance", 2, 2, False,
             [r"entire\s+maintenance|all\s+repairs|all\s+maintenance|sole\s+responsibility\s+for\s+(?:all\s+)?repairs"],
             [r"maintain|maintenance|repairs"]),
    RuleSpec("R08", "auto_renewal", 3, 2, False,
             [r"auto[-\s]?renews?|automatic(?:ally)?\s+renew|successive\s+\d+.*terms?|deemed\s+to\s+be\s+renewed|self[-\s]?renew"]),
    RuleSpec("R09", "unilateral_amendment", 4, 2, False,
             [r"may\s+(?:amend|modify|vary|alter).{0,60}(?:at\s+any\s+time|sole\s+discretion|without\s+(?:prior\s+)?notice)|unilateral.{0,40}(?:amend|modif|change)|sole\s+discretion.{0,60}(?:amend|modify|change)"]),
    RuleSpec("R10", "termination", 3, 2, False,
             [r"(?:landlord|company|owner)\s+may\s+terminate.{0,60}(?:without\s+notice|immediate|at\s+any\s+time)|terminate\s+with\s+immediate\s+effect"]),
    RuleSpec("R11", "indemnity", 4, 2, False,
             [r"indemnif\w*.{0,120}hold\s+harmless|hold\s+harmless.{0,120}indemnif\w*|indemnif\w*.{0,80}(?:any\s+and\s+all|unlimited|solely)"]),
    RuleSpec("R12", "liability", 3, 2, False,
             [r"aggregate\s+liability|liability.{0,40}capped?\s+at|cap(?:ped)?\s+(?:on|of)\s+liability|limitation\s+of\s+liability"]),
    RuleSpec("R13", "governing_law", 3, 1, True,
             [r"arbitration|arbitrat\w+|disputes?\s+shall\s+be\s+resolved\s+by"],
             [r"governed\s+by\s+the\s+laws|jurisdiction\s+of|subject\s+to\s+the\s+jurisdiction"]),
    RuleSpec("R14", "class_waiver", 2, 2, False,
             [r"class\s+action|class\s+waiver|waive\w*.{0,40}class\s+(?:action|proceedings)|collective\s+action.{0,40}waiv"]),
    RuleSpec("R15", "data_protection", 4, 2, False,
             [r"sell\w*.{0,40}data|sell\w*.{0,40}personal\s+information|shar\w*.{0,60}data.{0,40}third\s+part",
              r"data\s+processing\s+addendum|\bDPA\b|data\s+protection|personal\s+data.{0,40}protect|privacy\s+policy"],
             [r"data\s+processing\s+addendum|\bDPA\b|data\s+protection|personal\s+data.{0,40}protect"]),
    RuleSpec("R16", "retention", 3, 2, True,
             [r"retained\s+for|retention\s+(?:period\s+)?of|retain.{0,40}data.{0,40}(?:year|month)|deleted?\s+(?:thereafter|on\s+request)|deletion\s+of\s+data"],
             [r"retained\s+for|retention|deleted?\s+(?:thereafter|on\s+request)"]),
    RuleSpec("R17", "breach_notification", 3, 2, False,
             [r"notify.{0,40}breach.{0,40}(?:7|fifteen|30)\s*(?:days|day)|breach.{0,40}notif.{0,40}(?:week|month)",
              r"notify.{0,40}breach|breach.{0,40}notif|report.{0,40}(?:breach|incident).{0,40}(?:24|48|72)\s*hours?"]),
    RuleSpec("R18", "tds", 3, 2, False,
             [r"(?:tds|194[-\s]?i\s?b).{0,40}5\s*%|5\s*%.{0,40}(?:tds|194[-\s]?i\s?b)|deduct.{0,40}5\s*%\s*(?:tds|tax)",
              r"(?:tds|194[-\s]?i\s?b|tax\s+deducted)"]),
]

RULE_IDS = [r.rule_id for r in RULES]


def _num_word(raw: str) -> int | None:
    raw = raw.strip().lower().replace("  ", " ")
    if raw.isdigit():
        return int(raw)
    return _WORD_NUM.get(raw)


def parse_months(text: str) -> int | None:
    m = re.search(_MONTHS_RE, text, FLAGS)
    return _num_word(m.group(1)) if m else None


def parse_amount(text: str) -> float | None:
    m = re.search(_AMOUNT_RE, text, FLAGS)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def premise_kind(premise: str) -> str:
    p = premise.strip().lower()
    if p in ("residential", "res", "residence", "resi"):
        return "residential"
    if p in ("non-residential", "nonresidential", "non-res", "nonres", "commercial", "non-resi"):
        return "non-residential"
    return "unknown"


def window_for(text: str, at: int, need_end: int) -> tuple[int, int]:
    start = max(0, at - LEAD)
    end = min(len(text), start + WINDOW)
    if end < need_end:
        end = min(len(text), need_end)
        start = max(0, end - WINDOW)
    return start, end


def _hit(text: str, m: re.Match[str], rule: RuleSpec, tier: int, note: str = "",
         data: dict[str, str | float | bool] | None = None) -> Finding:
    s, e = window_for(text, m.start(), m.end())
    return Finding(rule_id=rule.rule_id, clause=rule.clause, excerpt=text[s:e],
                   start=s, end=e, status="hit", tier=tier, note=note, data=data or {})


def _present(text: str, m: re.Match[str], rule: RuleSpec, note: str = "",
             data: dict[str, str | float | bool] | None = None) -> Finding:
    s, e = window_for(text, m.start(), m.end())
    return Finding(rule_id=rule.rule_id, clause=rule.clause, excerpt=text[s:e],
                   start=s, end=e, status="pass", tier=rule.tier_pass, note=note, data=data or {})


def _absent(rule: RuleSpec, walkaway: bool) -> Finding:
    tier = 5 if walkaway else rule.tier_pass
    return Finding(rule_id=rule.rule_id, clause=rule.clause, excerpt="", start=0,
                   end=0, status="missing" if walkaway else "pass",
                   tier=tier, note="clause absent" + (" — walkaway" if walkaway else ""))


def _search(text: str, patterns: list[str]) -> re.Match[str] | None:
    for p in patterns:
        m = re.search(p, text, FLAGS)
        if m:
            return m
    return None


def _deposit_months_amount(text: str, m: re.Match[str]) -> tuple[int | None, float | None]:
    s, e = window_for(text, m.start(), m.end())
    scope = text[s:e]
    return parse_months(scope), parse_amount(scope)


def scan(text: str, premise: str = "residential") -> list[Finding]:
    """Scan one document; returns 18 findings in R01..R18 order."""
    kind = premise_kind(premise)
    out: list[Finding] = []
    for rule in RULES:
        out.append(_scan_rule(text, rule, kind))
    return out


def _scan_rule(text: str, rule: RuleSpec, kind: str) -> Finding:
    # Deferred: family matchers import helpers from here; top-level = cycle.
    from app.engine import rules_money, rules_safeguard

    rid = rule.rule_id
    if rid == "R01" and kind != "residential":
        return Finding(rule_id=rid, clause=rule.clause, excerpt="", start=0, end=0,
                       status="pass", tier=1, note="n/a for non-residential premise")
    if rid == "R02" and kind != "non-residential":
        return Finding(rule_id=rid, clause=rule.clause, excerpt="", start=0, end=0,
                       status="pass", tier=1, note="n/a for residential premise")
    if rid in ("R01", "R02"):
        return rules_money.deposit_rule(text, rule, kind)
    if rid == "R03":
        return rules_money.refund_rule(text, rule)
    if rid == "R04":
        return rules_money.overstay_rule(text, rule)
    if rid == "R05":
        return rules_money.revision_rule(text, rule)
    if rid == "R06":
        m = _search(text, rule.hit + rule.ok)
        if m:
            return _present(text, m, rule, "term/tenure stated")
        return _absent(rule, walkaway=True)
    if rid == "R07":
        mh = _search(text, rule.hit)
        if mh:
            return _hit(text, mh, rule, rule.tier_hit, "one-sided maintenance burden")
        m = _search(text, rule.ok)
        if m:
            return _present(text, m, rule, "maintenance clause present")
        return Finding(rule_id="R07", clause=rule.clause, excerpt="", start=0, end=0,
                       status="pass", tier=2, note="no maintenance clause — no risk")
    if rid == "R12":
        return rules_money.cap_rule(text, rule)
    if rid == "R13":
        return rules_safeguard.govlaw_rule(text, rule)
    if rid == "R15":
        return rules_safeguard.dpa_rule(text, rule)
    if rid == "R16":
        m = _search(text, rule.hit)
        if m:
            return _present(text, m, rule, "retention/deletion stated")
        return _absent(rule, walkaway=True)
    if rid == "R17":
        return rules_safeguard.breach_rule(text, rule)
    if rid == "R18":
        return rules_money.tds_rule(text, rule)
    m = _search(text, rule.hit)
    if m:
        return _hit(text, m, rule, rule.tier_hit)
    if rule.required:
        return _absent(rule, walkaway=True)
    return Finding(rule_id=rid, clause=rule.clause, excerpt="", start=0, end=0,
                   status="pass", tier=rule.tier_pass, note="clause absent — no risk")
