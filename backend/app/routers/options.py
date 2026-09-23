"""W3.1 POST /options — fight/settle/exit matrix + move-out + TDS checklists.

Statute numbers (plan section 7, verified Sep 2026): MTA Sec 11 (deposit caps
2mo res / 6mo non-res, refund within 1 month itemised), MTA Sec 23 (overstay
2x first 60d then 4x), Income-tax Sec 194-IB (2% since 1-Oct-2024, >Rs 50k/mo,
Form 26QC within 30d + Form 16C, no TAN; Sec 393(1)/Form 141 from TY26-27).
Options matrix only — never legal advice, disclaimer always attached.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

DISCLAIMER = "Information, not legal advice — verify with advocate"

router = APIRouter(tags=["options"])

OptionKind = Literal["fight", "settle", "exit"]


class OptionsRequest(BaseModel):
    job_id: str | None = None
    doc_id: str | None = None
    text: str | None = None
    premise: str = "residential"
    monthly_rent: float = 0.0
    pincode: str | None = None

    @model_validator(mode="after")
    def _needs_source(self) -> OptionsRequest:
        if not (self.job_id or self.doc_id or self.text):
            raise ValueError("provide job_id or doc_id or text")
        return self


class Option(BaseModel):
    kind: OptionKind
    title: str
    tradeoffs: list[str] = Field(default_factory=list)
    cost_hint: str = ""
    time_hint: str = ""


class OptionsResponse(BaseModel):
    options: list[Option] = Field(default_factory=list)
    move_out_checklist: list[str] = Field(default_factory=list)
    tds_checklist: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


def move_out_checklist() -> list[str]:
    """Move-out list: photos/bills/GST, 30-day clock, painting pro-rata."""
    return [
        "Photos + video of vacant possession with date stamp (all rooms, meters)",
        "Utility bills + GST invoices for repairs/painting, itemised deductions only (MTA Section 11)",
        "30-day refund clock: deposit refund within one month of vacant possession with itemised statement (MTA Sec 11)",
        "Painting pro-rata on 3yr life (3-year painting life; pay only remaining-life share)",
        "Handover letter signed by both parties with meter readings + keys",
        "Overstay guard: compensation 2x first 60 days then 4x (MTA Sec 23) — vacate on time",
    ]


def tds_checklist() -> list[str]:
    """TDS list: 2%, March deduct, 26QC by 30 Apr, 16C."""
    return [
        "Sec 194-IB: rent > Rs 50,000/mo → deduct 2% (cut from 5% on 1-Oct-2024; all FY25-26 at 2%)",
        "March deduct: deduct once-yearly in March (or last month of tenancy) for the full year",
        "Form 26QC within 30 days of deduction (by 30 Apr for March deduction) + Form 16C certificate to landlord",
        "No TAN needed; PAN-only filing (no-PAN payable capped at last-month rent)",
        "Note: renamed Sec 393(1)/Form 141 under Income-tax Act 2025 from TY26-27; companies use 194-I 10% instead",
    ]


def build_options(text: str, monthly_rent: float = 0.0, premise: str = "residential",
                  pincode: str | None = None) -> OptionsResponse:
    """Deterministic matrix from deposit/TDS posture (no advice verbs)."""
    _ = (text, pincode)
    rent_bit = f"Rs {monthly_rent:,.0f}/mo" if monthly_rent > 0 else "stated rent"
    options = [
        Option(
            kind="fight",
            title="Dispute deductions via Rent Authority notice",
            tradeoffs=[
                "Enforces MTA Sec 11 refund clock with itemised proof",
                "Preserves deposit claim but strains landlord relation",
            ],
            cost_hint="Filing fee + lawyer consult (indicative Rs 5–15k)",
            time_hint=f"4–12 weeks via Rent Authority ({rent_bit}, {premise})",
        ),
        Option(
            kind="settle",
            title="Negotiate itemised deductions + payment timeline",
            tradeoffs=[
                "Faster refund with agreed deductions schedule",
                "Needs written settlement to stay enforceable",
            ],
            cost_hint="Minimal cost; 1 consult to review settlement",
            time_hint="1–3 weeks of negotiation",
        ),
        Option(
            kind="exit",
            title="Vacate, document handover, claim via paper trail",
            tradeoffs=[
                "Clean exit with photos/bills/GST + 26QC/16C trail",
                "Gives up leverage on disputed deductions",
            ],
            cost_hint="Moving + documentation cost only",
            time_hint="Move-out week + 30-day refund clock",
        ),
    ]
    return OptionsResponse(options=options, move_out_checklist=move_out_checklist(),
                           tds_checklist=tds_checklist(), disclaimer=DISCLAIMER)


@router.post("/options", response_model=OptionsResponse)
def post_options(payload: OptionsRequest) -> OptionsResponse:
    """Return the fight/settle/exit matrix with checklists."""
    try:
        source = (payload.text or payload.job_id or payload.doc_id or "").strip()
        if not source:
            raise ValueError("provide job_id or doc_id or text")
        return build_options(source, monthly_rent=payload.monthly_rent,
                             premise=payload.premise, pincode=payload.pincode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
