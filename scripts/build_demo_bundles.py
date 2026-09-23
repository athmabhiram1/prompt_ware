"""W4.1 bundle builder — runs the frozen W2 engine LOCALLY (no live LLM calls).

Reads three source texts below, runs scan() + detect() + simplify_text() +
build_brief() + maths M1/M3, and writes deterministic frozen bundles to
data/preindex/{msa,nda,offer}.json. Re-run is byte-identical except built_at.

Usage (from repo root):
    python scripts/build_demo_bundles.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.engine import contradict, maths  # noqa: E402
from app.engine.rules import premise_kind, scan  # noqa: E402
from app.routers.brief import build_brief  # noqa: E402
from app.routers.simplify import simplify_text  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "preindex"

PRIYA_TEXT = (
    "RENTAL AGREEMENT - Priya Sharma, HSR Layout, Bengaluru (Karnataka). "
    "Monthly rent of Rs 30,000 for a 2BHK apartment. "
    "Security deposit of Rs 3,00,000 (ten months rent) held by the landlord. "
    "The initial term is eleven months starting 1 October 2026. "
    "The landlord may amend the terms of this agreement at any time "
    "at its sole discretion without prior notice. "
    "The tenant shall indemnify and hold harmless the landlord against "
    "any and all claims arising from the use of the premises. "
    "The landlord may share the tenant's personal data with third party "
    "marketing partners. "
    "Any disputes shall be resolved by arbitration in Bengaluru. "
    "The tenant shall deduct TDS at 2% under section 194-IB and deposit "
    "it with the government. "
    "On expiry the tenant shall hand over vacant possession."
)

MSME_TEXT = (
    "NON-DISCLOSURE AGREEMENT - Sharma Sweets (MSME), Indore. "
    "The receiving party shall protect all confidential information "
    "shared under this agreement. "
    "The receiving party may share confidential data with third party "
    "vendors without consent. "
    "This agreement shall auto-renew for successive 2 year terms "
    "unless terminated in writing. "
    "The company may terminate with immediate effect without notice. "
    "Data shall be retained for 5 years and deleted thereafter on request. "
    "Breach notifications shall be sent within 30 days of discovery."
)

DPDP_TEXT = (
    "OFFER LETTER - Junior Designer, PixelWorks Studio, Delhi. "
    "Monthly salary of Rs 60,000. "
    "The company may collect personal data including contact and identity "
    "details for employment purposes. "
    "Personal data shall be retained for 3 years after exit and deleted "
    "thereafter on written request. "
    "The company shall notify breaches within 72 hours to the Data "
    "Protection Board. "
    "The employee shall not disclose company trade secrets. "
    "TDS shall be deducted at 5% under section 194-IB on salary payments."
)


def _finding_dict(f):
    return {"rule_id": f.rule_id, "clause": f.clause, "excerpt": f.excerpt,
            "start": f.start, "end": f.end, "status": f.status,
            "tier": f.tier, "note": f.note, "data": dict(f.data)}


def _cite_span(text, excerpt):
    start = text.find(excerpt)
    assert start >= 0, f"excerpt not a span: {excerpt[:60]!r}"
    return start, start + len(excerpt)


def _qa_pair(text, question, finding, answer_tpl):
    excerpt = finding["excerpt"]
    s, e = _cite_span(text, excerpt)
    answer = f"{answer_tpl} [doc p.1]"
    return {"question": question, "answer": answer,
            "citations": [{"page": 1, "span": excerpt,
                           "start": s, "end": e}],
            "abstain": None}


def build_demo(demo_id, bundle_file, doc_id, title, story, text,
               premise, pincode, qa_specs, obligations):
    kind = premise_kind(premise)
    findings = scan(text, kind)
    fd = [_finding_dict(f) for f in findings]
    risks = [f for f in fd if f["status"] == "hit" and f["excerpt"]]
    missing = [f for f in fd if f["status"] == "missing"]
    contras = [{"cid": c.cid, "excerpt": c.excerpt, "start": c.start,
                "end": c.end, "note": c.note}
               for c in contradict.detect(text, findings)]
    simp = simplify_text(text, level="8")
    brief = build_brief(text, premise=premise, pincode=pincode, job_id=doc_id)

    by_rule = {f["rule_id"]: f for f in fd if f["excerpt"]}
    qa = []
    for spec in qa_specs:
        if spec.get("abstain"):
            qa.append({"question": spec["question"], "answer": None,
                       "citations": [],
                       "abstain": {"reason": spec["reason"], "code": spec["code"]}})
        else:
            qa.append(_qa_pair(text, spec["question"],
                               by_rule[spec["rule"]], spec["answer"]))

    return {
        "demo_id": demo_id,
        "bundle": bundle_file,
        "doc_id": doc_id,
        "title": title,
        "story": story,
        "premise": premise,
        "pincode": pincode,
        "text": text,
        "docs": [{"doc_id": doc_id, "name": f"{doc_id}.txt", "text": text}],
        "audit": {"risks": risks, "missing": missing,
                  "obligations": obligations, "contradictions": contras,
                  "rule_count": len(fd)},
        "simplify": json.loads(simp.model_dump_json()),
        "qa": qa,
        "brief": json.loads(brief.model_dump_json()),
        "meta": {"built_at": datetime.now(timezone.utc).isoformat(),
                 "engine": "app.engine.rules R01-R18 + maths M1/M2/M3 + contradict C1-C4",
                 "llm_live": False, "served_from": "cache", "cost_usd": 0.0,
                 "served": "cache-first when LLM_LIVE=0 or Aura paused"},
    }


def main():
    m1 = maths.check_deposit(300000, 30000, "residential")
    m3_priya = maths.tds_194ib(30000)
    priya_obligations = [
        {"id": "OBL-1", "statute": "MTA Sec 11", "duty": "deposit cap 2 months residential",
         "computed": f"cap Rs {m1.cap_amount:.0f}, deposit Rs 300000, excess Rs {m1.excess:.0f}, breach={m1.breach}",
         "deadline": "refund within 30 days of vacant possession with itemised statement",
         "source_rule": "R01"},
        {"id": "OBL-2", "statute": "MTA Sec 11", "duty": "30-day refund clock",
         "computed": "deposit Rs 3,00,000 (10x rent Rs 30,000) vs cap Rs 60,000",
         "deadline": "one month of vacant possession",
         "source_rule": "R03"},
        {"id": "OBL-3", "statute": "Sec 194-IB", "duty": "TDS on rent",
         "computed": f"rent Rs 30000 <= Rs 50000 threshold, applicable={m3_priya.applicable}, rate 2% since 1-Oct-2024",
         "deadline": "Form 26QC within 30 days + Form 16C, no TAN",
         "source_rule": "R18"},
    ]
    msme_obligations = [
        {"id": "OBL-1", "statute": "DPDP Act 2023", "duty": "breach notification",
         "computed": "agreement allows 30 days; DPDP expects breach notice within 72 hours",
         "deadline": "72 hours to Data Protection Board",
         "source_rule": "R17"},
        {"id": "OBL-2", "statute": "DPDP Act 2023", "duty": "retention + deletion on request",
         "computed": "retained 5 years, deleted thereafter on request",
         "deadline": "delete on request after 5 years",
         "source_rule": "R16"},
    ]
    dpdp_obligations = [
        {"id": "OBL-1", "statute": "Sec 194-IB", "duty": "correct outdated TDS rate",
         "computed": "agreement cites 5%; current rate 2% since 1-Oct-2024",
         "deadline": "Form 26QC within 30 days + Form 16C",
         "source_rule": "R18"},
        {"id": "OBL-2", "statute": "DPDP Act 2023", "duty": "retention + deletion on request",
         "computed": "retained 3 years after exit, deleted thereafter on written request",
         "deadline": "delete on written request after 3 years",
         "source_rule": "R16"},
    ]

    demos = [
        build_demo(
            "priya", "msa.json", "demo-priya-lease",
            "Priya's Bengaluru rental lease - Rs 30k rent, Rs 3L deposit",
            "Priya (tenant, HSR Layout Bengaluru) pays Rs 30,000/month rent with a "
            "Rs 3,00,000 deposit (10x rent). MTA Sec 11 caps residential deposits at "
            "2 months and is persuasive-only in Karnataka; 194-IB TDS is 2%; the "
            "refund clock is 30 days.",
            PRIYA_TEXT, "residential", "560001",
            [{"question": "Is the Rs 3,00,000 security deposit legal?",
              "rule": "R01",
              "answer": "No - the Rs 3,00,000 deposit is 10x the Rs 30,000 rent, far above the 2-month MTA Sec 11 cap"},
             {"question": "Can the landlord change the agreement terms unilaterally?",
              "rule": "R09",
              "answer": "The agreement lets the landlord amend terms at any time at its sole discretion without notice"},
             {"question": "What is the monthly maintenance charge?",
              "abstain": True,
              "reason": "document does not contain sufficient information to answer [NO_EVIDENCE]",
              "code": "NO_EVIDENCE"}],
            priya_obligations),
        build_demo(
            "msme", "nda.json", "demo-msme-nda",
            "Sharma Sweets (MSME) mutual NDA - auto-renewal + termination",
            "An Indore MSME signs a vendor NDA with auto-renewal for successive "
            "2-year terms, unilateral immediate termination, and third-party data "
            "sharing without consent.",
            MSME_TEXT, "non-residential", "452001",
            [{"question": "Does the NDA auto-renew?",
              "rule": "R08",
              "answer": "Yes - it auto-renews for successive 2 year terms unless terminated in writing"},
             {"question": "Can the company terminate immediately?",
              "rule": "R10",
              "answer": "Yes - the company may terminate with immediate effect without notice"}],
            msme_obligations),
        build_demo(
            "dpdp", "offer.json", "demo-dpdp-offer",
            "PixelWorks offer letter - retention + outdated TDS",
            "A Delhi offer letter with 3-year post-exit retention, 72-hour breach "
            "notice, and an outdated 5% TDS cite (current 2% since 1-Oct-2024).",
            DPDP_TEXT, "non-residential", "110001",
            [{"question": "How long is personal data retained?",
              "rule": "R16",
              "answer": "Personal data is retained for 3 years after exit and deleted thereafter on written request"},
             {"question": "Is the 5% TDS rate correct?",
              "rule": "R18",
              "answer": "No - the agreement cites 5% but the current 194-IB rate is 2% since 1-Oct-2024"}],
            dpdp_obligations),
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for bundle in demos:
        path = OUT_DIR / bundle["bundle"]
        path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        risks = bundle["audit"]["risks"]
        highs = sum(1 for r in risks if r["tier"] >= 4)
        print(f"wrote {path}: {len(risks)} risks ({highs} HIGH), "
              f"{len(bundle['audit']['missing'])} missing, "
              f"{len(bundle['audit']['contradictions'])} contradictions, "
              f"{len(bundle['qa'])} qa")
    print("zero live calls made (engine + deterministic simplify/brief only)")


if __name__ == "__main__":
    main()
