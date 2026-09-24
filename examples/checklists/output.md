# Checklists — Output (deterministic engines)

Ran: `move_out_checklist()` + `tds_checklist()` at `options.py:54,66` + `build_ics(...)` at `export.py:30`.

**Move-out checklist (`options.py:54`):**
```
- Photos + video of vacant possession with date stamp (all rooms, meters)
- Utility bills + GST invoices for repairs/painting, itemised deductions only (MTA Section 11)
- 30-day refund clock: deposit refund within one month of vacant possession with itemised statement (MTA Sec 11)
- Painting pro-rata on 3yr life (3-year painting life; pay only remaining-life share)
- Handover letter signed by both parties with meter readings + keys
- Overstay guard: compensation 2x first 60 days then 4x (MTA Sec 23) — vacate on time
```

**TDS checklist (`options.py:66`):**
```
- Sec 194-IB: rent > Rs 50,000/mo → deduct 2% (cut from 5% on 1-Oct-2024; all FY25-26 at 2%)
- March deduct: deduct once-yearly in March (or last month of tenancy) for the full year
- Form 26QC within 30 days of deduction (by 30 Apr for March deduction) + Form 16C certificate to landlord
- No TAN needed; PAN-only filing (no-PAN payable capped at last-month rent)
- Note: renamed Sec 393(1)/Form 141 under Income-tax Act 2025 from TY26-27; companies use 194-I 10% instead
```

**Calendar export (`GET /export.ics` at `export.py:66`):**
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NyayaMitra//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:brief@nyayamitra
DTSTAMP:20260501T100000Z
DTSTART:20260501T100000
DTEND:20260501T110000
SUMMARY:Deposit refund deadline
DESCRIPTION:Deposit refund deadline — Information, not legal advice — verify with advocate
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Deposit refund deadline
TRIGGER:-PT24H
END:VALARM
END:VEVENT
END:VCALENDAR
```

**Maths proof (deterministic at `maths.py`):**
- `check_deposit(300000,30000,"residential")` → `{cap_months:2, cap_amount:60000.0, excess:240000.0, breach:true, refund_within_days:30}` at `maths.py:67`.
- `overstay_charge(30000,75)` → `{daily_rent:1000.0, first_slab:120000.0, after_slab:60000.0, total:180000.0}`.
- `tds_194ib(60000,12)` → `{applicable:true, rate:0.02, yearly_tds:14400.0, form:"26QC", cert:"16C", payable_capped:14400.0}`.

**Routes:** `POST /options` at `options.py:126`; `GET /export.ics` at `export.py:66`.

*LLM-drafted: none — all three lists are static deterministic strings plus maths at maths.py.*
