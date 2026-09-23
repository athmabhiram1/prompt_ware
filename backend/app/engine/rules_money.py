"""Money-family matchers: R01/R02 deposit caps, R03 refund, R04 overstay,
R05 revision notice, R12 liability cap, R18 TDS rate."""

from app.engine.rules import (
    Finding,
    RuleSpec,
    _absent,
    _deposit_months_amount,
    _hit,
    _present,
    _search,
    parse_months,
    window_for,
)


def deposit_rule(text: str, rule: RuleSpec, kind: str) -> Finding:
    m = _search(text, rule.hit)
    if not m:
        return _absent(rule, walkaway=True)
    months, amount = _deposit_months_amount(text, m)
    cap = 2 if kind == "residential" else 6
    data: dict[str, str | float | bool] = {"cap_months": cap}
    if months is not None:
        data["months"] = months
    if amount is not None:
        data["amount"] = amount
    if months is not None and months > cap:
        return _hit(text, m, rule, rule.tier_hit,
                    f"deposit {months}mo exceeds {cap}mo statutory cap", data)
    return _present(text, m, rule, "deposit within statutory cap", data)


def refund_rule(text: str, rule: RuleSpec) -> Finding:
    dep = _search(text, [r"security\s*deposit|deposit\s*(?:of|amount|is)"])
    if not dep:
        return Finding(rule_id="R03", clause=rule.clause, excerpt="", start=0, end=0,
                       status="pass", tier=1, note="no deposit — no refund duty")
    m = _search(text, rule.ok)
    if m and _search(text, [r"itemis|itemiz"]):
        return _present(text, m, rule, "1-month itemised refund on vacant possession")
    m2 = _search(text, [r"refund\w*"])
    if m2:
        return _hit(text, m2, rule, rule.tier_hit, "refund lacks 1-month itemised statement")
    return _hit(text, dep, rule, rule.tier_hit, "deposit without refund timeline")


def overstay_rule(text: str, rule: RuleSpec) -> Finding:
    m = _search(text, rule.hit)
    if not m:
        return Finding(rule_id="R04", clause=rule.clause, excerpt="", start=0, end=0,
                       status="pass", tier=2, note="no overstay clause — no risk")
    if _search(text, rule.ok):
        return _present(text, m, rule, "statutory 2x/4x multipliers disclosed")
    return _hit(text, m, rule, rule.tier_hit, "overstay without statutory multipliers")


def revision_rule(text: str, rule: RuleSpec) -> Finding:
    m = _search(text, rule.hit)
    if not m:
        return Finding(rule_id="R05", clause=rule.clause, excerpt="", start=0, end=0,
                       status="pass", tier=2, note="no revision clause — no risk")
    s, e = window_for(text, m.start(), m.end())
    months = parse_months(text[s:e])
    data: dict[str, str | float | bool] = {}
    if months is not None:
        data["notice_months"] = months
    if months is not None and months < 3:
        return _hit(text, m, rule, rule.tier_hit, f"revision notice {months}mo < 3mo", data)
    return _present(text, m, rule, "revision clause present", data)


def cap_rule(text: str, rule: RuleSpec) -> Finding:
    m = _search(text, rule.hit)
    if not m:
        return Finding(rule_id="R12", clause=rule.clause, excerpt="", start=0, end=0,
                       status="pass", tier=2, note="no liability cap — no risk")
    s, e = window_for(text, m.start(), m.end())
    months = parse_months(text[s:e])
    data: dict[str, str | float | bool] = {}
    if months is not None:
        data["months"] = months
    if months is not None and months > 12:
        return _hit(text, m, rule, rule.tier_hit, f"cap {months}mo exceeds 12mo norm", data)
    return _present(text, m, rule, "cap within 12mo norm", data)


def tds_rule(text: str, rule: RuleSpec) -> Finding:
    m = _search(text, [rule.hit[0]])
    if m:
        return _hit(text, m, rule, rule.tier_hit, "outdated 5% TDS rate (current 2% since 1-Oct-2024)")
    m = _search(text, [rule.hit[1]])
    if m:
        return _present(text, m, rule, "TDS clause present at current rate")
    return Finding(rule_id="R18", clause=rule.clause, excerpt="", start=0, end=0,
                   status="pass", tier=2, note="no TDS clause — no risk")
