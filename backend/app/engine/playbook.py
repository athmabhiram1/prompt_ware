"""12-clause playbook (+deposit/tenure) with tiers T1-T5 and JSON schema.

Removed-protection rule: a clause present in v1 at tier ≤2 that is missing
or tier ≥4 in v2 is a 🔴 loss — surfaced in `removed_protections`.
Missing critical clause (deposit, tenure, governing_law, retention) forces
verdict `walkaway`; no LLM override is permitted.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.engine.rules import Finding

Verdict = Literal["pass", "caution", "walkaway"]

RULE_TO_CLAUSE: dict[str, str] = {
    "R01": "deposit",
    "R02": "deposit",
    "R03": "deposit",
    "R04": "overstay",
    "R05": "price",
    "R06": "tenure",
    "R07": "maintenance",
    "R08": "termination",
    "R09": "termination",
    "R10": "termination",
    "R11": "indemnity",
    "R12": "liability",
    "R13": "governing_law",
    "R14": "termination",
    "R15": "data_protection",
    "R16": "retention",
    "R17": "data_protection",
    "R18": "price",
}


class ClauseSpec(BaseModel):
    name: str
    tier: int = Field(ge=1, le=5)
    required: bool = False
    missing_walkaway: bool = False


PLAYBOOK: dict[str, ClauseSpec] = {
    "liability": ClauseSpec(name="liability", tier=2),
    "indemnity": ClauseSpec(name="indemnity", tier=3),
    "confidentiality": ClauseSpec(name="confidentiality", tier=2),
    "data_protection": ClauseSpec(name="data_protection", tier=2),
    "ip": ClauseSpec(name="ip", tier=2),
    "sla": ClauseSpec(name="sla", tier=3),
    "audit": ClauseSpec(name="audit", tier=3),
    "ai_use": ClauseSpec(name="ai_use", tier=3),
    "termination": ClauseSpec(name="termination", tier=2),
    "governing_law": ClauseSpec(
        name="governing_law", tier=1, required=True, missing_walkaway=True
    ),
    "retention": ClauseSpec(
        name="retention", tier=2, required=True, missing_walkaway=True
    ),
    "price": ClauseSpec(name="price", tier=3),
    "deposit": ClauseSpec(name="deposit", tier=1, required=True, missing_walkaway=True),
    "tenure": ClauseSpec(name="tenure", tier=2, required=True, missing_walkaway=True),
    "overstay": ClauseSpec(name="overstay", tier=3),
    "maintenance": ClauseSpec(name="maintenance", tier=2),
}

WALKAWAY_CLAUSES = {n for n, c in PLAYBOOK.items() if c.missing_walkaway}


class PlaybookSchema(BaseModel):
    """JSON-schema carrier for the playbook (legal-redline-tools compatible)."""

    version: str = "w2.2"
    clauses: dict[str, ClauseSpec] = PLAYBOOK  # type: ignore[assignment]
    walkaway_clauses: list[str] = sorted(WALKAWAY_CLAUSES)


def playbook_json_schema() -> dict:
    return PlaybookSchema.model_json_schema()


def clause_states(findings: list[Finding]) -> dict[str, str | int]:
    """Best (lowest-tier, present-first) state per playbook clause."""
    states: dict[str, dict[str, str | int]] = {}
    for f in findings:
        clause = RULE_TO_CLAUSE.get(f.rule_id, f.clause)
        if clause not in PLAYBOOK:
            continue
        cur = states.get(clause)
        rank = (0 if f.status != "missing" else 1, f.tier)
        if cur is None or rank < (cur["rank0"], cur["tier"]):
            states[clause] = {"rank0": rank[0], "tier": f.tier, "status": f.status}
    return {k: v["status"] for k, v in states.items()}


def removed_protection(a: list[Finding], b: list[Finding]) -> list[str]:
    """Rule-level 🔴: v1 present at tier ≤2, v2 missing/empty/≥4 → clause lost."""
    mb = {f.rule_id: f for f in b}
    lost: set[str] = set()
    for fa in a:
        if fa.status == "missing" or not fa.excerpt or fa.tier > 2:
            continue
        fb = mb.get(fa.rule_id)
        if fb is None or fb.status == "missing" or not fb.excerpt or fb.tier >= 4:
            lost.add(RULE_TO_CLAUSE.get(fa.rule_id, fa.clause))
    return sorted(lost)


def verdict(findings: list[Finding]) -> Verdict:
    states = clause_states(findings)
    if any(states.get(c) == "missing" for c in WALKAWAY_CLAUSES):
        return "walkaway"
    if any(f.status == "hit" and f.tier >= 4 for f in findings):
        return "caution"
    return "pass"
