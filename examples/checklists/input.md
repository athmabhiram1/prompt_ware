# Checklists — Input

Source: `samples/v2-landlord-amend.md` (or any doc — checklists are **statute-anchored**, not doc-parsed)

Request:
```
POST /options {text:<any>, monthly_rent:30000} → {move_out_checklist, tds_checklist}
GET /export.ics?job_id=brief&title=Deposit%20refund%20deadline&dtstart=20260501T100000
```

Engines:
- Move-out: `backend/app/routers/options.py:54 move_out_checklist` (MTA Sec 11 + Sec 23)
- TDS: `backend/app/routers/options.py:66 tds_checklist` (194-IB 2% since 1-Oct-2024)
- Calendar: `backend/app/routers/export.py:30 build_ics` (RFC5545 VEVENT+VALARM)
