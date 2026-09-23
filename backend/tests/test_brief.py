"""W3.1 brief/options/ICS — TDD gate (RED first, stubbed W2 outputs, LLM_LIVE=0).

Covers: brief cites W2 outputs (ValidationError on uncited claim), options
fight/settle/exit + checklists with statute numbers, ICS VEVENT+VALARM+DTSTART
structure, disclaimer present everywhere. No live LLM.
"""

import re
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LEASE = (
    "Security deposit of Rs 60,000 (two months rent) held by the landlord. "
    "It shall be refunded within one month of vacant possession after due "
    "deductions with an itemised statement. "
    "Rent of Rs 60,000 per month. The tenant shall deduct TDS at 2% "
    "under section 194-IB and deposit it with the government. "
    "On expiry the tenant shall hand over vacant possession."
)

DISCLAIMER = "Information, not legal advice"


def test_brief_module_imports():
    from app.routers import brief, export, options  # noqa: F401

    assert brief.DISCLAIMER.startswith("Information, not legal advice")
    assert options.DISCLAIMER.startswith("Information, not legal advice")


def test_brief_rejects_uncited_claim():
    from app.routers.brief import assert_all_cited

    with pytest.raises(ValidationError):
        assert_all_cited(["The deposit is excessive with no cite."])


def test_brief_cites_w2_outputs():
    from app.routers.brief import build_brief

    resp = build_brief(text=LEASE, premise="residential", pincode="560001")
    assert DISCLAIMER in resp.markdown
    assert DISCLAIMER in resp.disclaimer
    for section in ("Facts", "Risks", "Missing", "Deadlines", "Questions"):
        assert section.lower() in resp.markdown.lower()
    # every bullet claim carries a [doc p.X] cite — zero invented cites
    bullets = [ln for ln in resp.markdown.splitlines() if ln.strip().startswith("-")]
    assert len(bullets) >= 5
    for bullet in bullets:
        assert re.search(r"\[doc p\.\d+\]", bullet), bullet
    # verification trail per iPleaders pattern
    assert len(resp.verification_trail) >= 1
    for row in resp.verification_trail:
        assert row.source and row.section and row.timestamp
    assert len(resp.questions_for_lawyer) in (2, 3)
    # cites reuse W2 spans: excerpt slices source
    for cite in resp.cites:
        assert LEASE[cite.start:cite.end] == cite.excerpt


def test_options_matrix_and_checklists():
    from app.routers.options import build_options

    resp = build_options(text=LEASE, monthly_rent=60000.0, premise="residential", pincode="560001")
    kinds = {o.kind for o in resp.options}
    assert kinds == {"fight", "settle", "exit"}
    for opt in resp.options:
        assert opt.tradeoffs and opt.cost_hint and opt.time_hint
        assert "sue" not in opt.title.lower()  # options matrix, never advice
    assert DISCLAIMER in resp.disclaimer
    moveout = "\n".join(resp.move_out_checklist)
    assert "30-day" in moveout or "30 day" in moveout or "within one month" in moveout
    assert "Sec 11" in moveout or "Section 11" in moveout
    assert "3yr" in moveout or "3-year" in moveout or "3 year" in moveout
    tds = "\n".join(resp.tds_checklist)
    assert "2%" in tds
    assert "26QC" in tds
    assert "16C" in tds
    assert "194-IB" in tds


def test_ics_has_vevent_valarm_dtstart():
    from app.routers.export import build_ics

    ics = build_ics(job_id="t-lease", title="TDS filing reminder", dtstart="20260430T100000")
    assert "BEGIN:VEVENT" in ics
    assert "END:VEVENT" in ics
    assert "BEGIN:VALARM" in ics
    assert "TRIGGER" in ics
    assert re.search(r"DTSTART:\d{8}T\d{6}", ics)
    assert "DTSTAMP" in ics
    assert "UID" in ics
    assert DISCLAIMER in ics or "verify with advocate" in ics


def test_endpoints_brief_options_ics():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.brief import router as brief_router
    from app.routers.export import router as export_router
    from app.routers.options import router as options_router

    app = FastAPI()
    app.include_router(brief_router)
    app.include_router(options_router)
    app.include_router(export_router)
    client = TestClient(app)

    b = client.post("/brief", json={"text": LEASE, "premise": "residential"})
    assert b.status_code == 200, b.text
    assert DISCLAIMER in b.json()["markdown"]

    o = client.post("/options", json={"text": LEASE, "monthly_rent": 60000.0})
    assert o.status_code == 200, o.text
    assert len(o.json()["options"]) == 3

    ics = client.get("/export.ics", params={"job_id": "t-lease", "title": "TDS reminder"})
    assert ics.status_code == 200, ics.text
    assert "BEGIN:VEVENT" in ics.text
    assert "BEGIN:VALARM" in ics.text
