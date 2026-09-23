"""W2.2 compare vertical — 6 plan fixtures (TDD RED first).

Every hit asserts byte-identical excerpts: doc[start:end] == excerpt.
No live LLM here: regex + maths only; judge path uses threshold constants.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.engine.maths import TDS_RATE, check_deposit, overstay_charge, tds_194ib
from app.engine.rules import RULE_IDS, scan

RENT = 30000

F1 = {
    "premise": "residential",
    "v1": "Security deposit of Rs 60,000 (two months rent) held by the landlord. "
    "It shall be refunded within one month of vacant possession after due "
    "deductions with an itemised statement.",
    "v2": "Security deposit of Rs 1,80,000 (six months rent) held by the landlord. "
    "It shall be refunded within one month of vacant possession after due "
    "deductions with an itemised statement.",
}
F2 = {
    "premise": "non-residential",
    "v1": "Security deposit of Rs 6,00,000 (six months rent) for the commercial premises. "
    "Refund within one month of vacant possession after due deductions with itemised statement. "
    "Confidentiality: both parties shall keep shared information confidential. "
    "This agreement is governed by the laws of India.",
    "v2": "Security deposit of Rs 6,00,000 (six months rent) for the commercial premises. "
    "Refund within one month of vacant possession after due deductions with itemised statement. "
    "Confidentiality: both parties shall keep shared information confidential. "
    "This agreement is governed by the laws of India.",
}
F3 = {
    "premise": "residential",
    "v1": "On expiry the tenant shall hand over vacant possession.",
    "v2": "On expiry the tenant shall hand over vacant possession. If the tenant "
    "overstays, compensation is twice the monthly rent for the first two months "
    "and four times the monthly rent thereafter.",
}
F4 = {
    "premise": "residential",
    "v1": "Rent of Rs 60,000 per month. TDS will be deducted as applicable.",
    "v2": "Rent of Rs 60,000 per month. The tenant shall deduct TDS at 5% "
    "under section 194-IB and deposit it with the government.",
}
F5 = {
    "premise": "residential",
    "v1": "Security deposit of Rs 60,000 (two months rent). Personal data shall be "
    "retained for 3 years and deleted thereafter on request. "
    "This agreement is governed by the laws of India.",
    "v2": "Security deposit of Rs 60,000 (two months rent). "
    "This agreement is governed by the laws of India.",
}
F6 = {
    "premise": "commercial",
    "v1": "The tenant shall maintain the premises in good repair. The aggregate "
    "liability of either party is capped at 12 months fees. "
    "A data processing addendum (DPA) is attached as Annexure A.",
    "v2": "The tenant may maintain the premises in good repair. The aggregate "
    "liability of either party is capped at 36 months fees. This agreement "
    "auto-renews for successive 12-month terms unless either party gives 60 days "
    "notice. Disputes shall be resolved by binding arbitration in Mumbai.",
}


def _client() -> TestClient:
    from app.routers.compare import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _resp(f: dict) -> dict:
    r = _client().post("/compare", json={"a": f["v1"], "b": f["v2"]})
    assert r.status_code == 200, r.text
    return r.json()


def _by_rule(resp: dict, rule: str) -> list:
    out = []
    for d in resp["deltas"]:
        if any(c["rule_id"] == rule for c in d["cites"]):
            out.append(d)
    return out


def _assert_excerpts(doc: str, cites: list) -> None:
    for c in cites:
        assert doc[c["start"] : c["end"]] == c["excerpt"], c["rule_id"]
        assert len(c["excerpt"]) <= 800


def test_f1_deposit_breach_r01_t4() -> None:
    resp = _resp(F1)
    ds = _by_rule(resp, "R01")
    assert any(d["label"] == "risk-up" for d in ds)
    assert check_deposit(180000, RENT, "residential").excess == 120000
    assert scan(F1["v2"], F1["premise"])[0].tier == 4  # R01 is first
    assert set(RULE_IDS) >= {"R01", "R18"} and len(RULE_IDS) == 18


def test_f2_compliant_commercial_no_risk_up() -> None:
    resp = _resp(F2)
    assert all(d["label"] != "risk-up" for d in resp["deltas"])
    assert resp["coverage"]["v2"] >= resp["coverage"]["v1"]
    _assert_excerpts(F2["v1"], [c for d in resp["deltas"] for c in d["cites"] if c["side"] == "v1"])


def test_f3_overstay_m2_pro_rata() -> None:
    got = overstay_charge(RENT, 75)
    assert got.total == 180000.0  # 60d x 2x + 15d x 4x at Rs1000/day
    resp = _resp(F3)
    assert any(d["label"] in ("clarified", "added") for d in _by_rule(resp, "R04"))


def test_f4_outdated_tds_c4_and_m3_rate() -> None:
    assert TDS_RATE == 0.02
    got = tds_194ib(60000)
    assert got.applicable and got.yearly_tds == 14400.0 and got.form == "26QC"
    resp = _resp(F4)
    assert any(d["label"] in ("risk-up", "added") for d in _by_rule(resp, "R18"))
    assert "C4" in {c["rule_id"] for d in resp["deltas"] for c in d["cites"]}


def test_f5_missing_retention_walkaway() -> None:
    resp = _resp(F5)
    assert "retention" in resp["removed_protections"]
    assert resp["verdict"] == "walkaway"
    _assert_excerpts(F1["v1"], [c for d in _resp(F1)["deltas"] for c in d["cites"] if c["side"] == "v1"])


def test_f6_autorenew_arbitration_traps() -> None:
    resp = _resp(F6)
    assert any(d["label"] == "added" for d in _by_rule(resp, "R08"))
    assert any(d["label"] == "added" for d in _by_rule(resp, "R13"))
    assert any(d["label"] == "risk-up" for d in _by_rule(resp, "R12"))
    assert any("shall" in d["one_liner"] for d in resp["deltas"])
    assert "data_protection" in resp["removed_protections"]
    _assert_excerpts(F6["v2"], [c for d in resp["deltas"] for c in d["cites"] if c["side"] == "v2"])
