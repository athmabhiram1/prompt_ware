"""Safeguard-family matchers: R13 governing law/arbitration, R15 data
protection/DPA, R17 breach notification."""

from app.engine.rules import Finding, RuleSpec, _absent, _hit, _present, _search


def govlaw_rule(text: str, rule: RuleSpec) -> Finding:
    arb = _search(text, rule.hit)
    gov = _search(text, rule.ok)
    if arb:
        return _hit(text, arb, rule, rule.tier_hit, "arbitration clause — review venue/seat")
    if gov:
        return _present(text, gov, rule, "governing law stated")
    return _absent(rule, walkaway=True)


def dpa_rule(text: str, rule: RuleSpec) -> Finding:
    if _search(text, [rule.hit[0]]):
        m = _search(text, [rule.hit[0]])
        assert m is not None
        return _hit(text, m, rule, rule.tier_hit, "personal data shared/sold")
    m = _search(text, rule.ok)
    if m:
        return _present(text, m, rule, "data protection present")
    return Finding(rule_id="R15", clause=rule.clause, excerpt="", start=0, end=0,
                   status="missing", tier=4, note="no data protection — removed-protection watch")


def breach_rule(text: str, rule: RuleSpec) -> Finding:
    if _search(text, [rule.hit[0]]):
        m = _search(text, [rule.hit[0]])
        assert m is not None
        return _hit(text, m, rule, rule.tier_hit, "breach notification slower than 72h")
    m = _search(text, [rule.hit[1]])
    if m:
        return _present(text, m, rule, "breach notification within 72h")
    return Finding(rule_id="R17", clause=rule.clause, excerpt="", start=0, end=0,
                   status="pass", tier=2, note="no breach clause — no risk")
