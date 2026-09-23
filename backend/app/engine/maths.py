"""M1/M2/M3 exact maths (Model Tenancy Act + Income-tax 194-IB).

M1: deposit cap 2mo residential / 6mo non-residential (MTA Sec 11); refund on
    vacant possession after due deductions, within 1 month, itemised only.
M2: overstay compensation pro-rata daily — 2x first 60 days, 4x after (Sec 23).
M3: 194-IB TDS on rent > Rs 50,000/month — 2% yearly since 1-Oct-2024
    (all FY25-26 at 2%), Form 26QC within 30 days + Form 16C, no TAN/PAN-only;
    no-PAN payable capped at min(tds, last-month rent).
"""

from datetime import date

from pydantic import BaseModel, Field

M1_RES_MONTHS = 2
M1_NONRES_MONTHS = 6
M1_REFUND_DAYS = 30
M2_FIRST_DAYS = 60
M2_FIRST_MULT = 2.0
M2_AFTER_MULT = 4.0
M2_DAY_BASE = 30.0
TDS_RATE = 0.02
TDS_THRESHOLD = 50000.0
TDS_CUTOFF = date(2024, 10, 1)
TDS_FORM = "26QC"
TDS_CERT = "16C"
TDS_FORM_DAYS = 30


class DepositResult(BaseModel):
    cap_months: int
    cap_amount: float
    excess: float
    breach: bool
    refund_within_days: int = M1_REFUND_DAYS


class OverstayResult(BaseModel):
    days: int
    daily_rent: float
    first_slab: float = Field(description="2x charge for first 60 days")
    after_slab: float = Field(description="4x charge after 60 days")
    total: float


class TdsResult(BaseModel):
    applicable: bool
    rate: float = TDS_RATE
    yearly_tds: float
    form: str = TDS_FORM
    form_within_days: int = TDS_FORM_DAYS
    cert: str = TDS_CERT
    tan_required: bool = False
    payable_capped: float = Field(description="no-PAN cap: min(tds, last-month rent)")


def _premise_cap(premise: str) -> int:
    from app.engine.rules import premise_kind

    return M1_RES_MONTHS if premise_kind(premise) != "non-residential" else M1_NONRES_MONTHS


def check_deposit(deposit: float, monthly_rent: float, premise: str = "residential") -> DepositResult:
    cap_months = _premise_cap(premise)
    cap_amount = cap_months * monthly_rent
    excess = max(0.0, deposit - cap_amount)
    return DepositResult(cap_months=cap_months, cap_amount=cap_amount,
                         excess=excess, breach=excess > 0)


def overstay_charge(monthly_rent: float, days: int) -> OverstayResult:
    daily = monthly_rent / M2_DAY_BASE
    first_n = min(days, M2_FIRST_DAYS)
    after_n = max(0, days - M2_FIRST_DAYS)
    first = first_n * daily * M2_FIRST_MULT
    after = after_n * daily * M2_AFTER_MULT
    return OverstayResult(days=days, daily_rent=daily, first_slab=first,
                          after_slab=after, total=first + after)


def tds_194ib(monthly_rent: float, months: int = 12) -> TdsResult:
    applicable = monthly_rent > TDS_THRESHOLD
    yearly = monthly_rent * months * TDS_RATE if applicable else 0.0
    capped = min(yearly, monthly_rent) if applicable else 0.0
    return TdsResult(applicable=applicable, yearly_tds=yearly, payable_capped=capped)
