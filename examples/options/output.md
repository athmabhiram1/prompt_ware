# Options — Output (deterministic engine)

Ran: `build_options(v2_text, monthly_rent=30000, premise="residential", pincode="560034")` at `backend/app/routers/options.py:77`.

**Result (engine-derived):**
```json
{
  "options": [
    {"kind":"fight","title":"Dispute deductions via Rent Authority notice","tradeoffs":["Enforces MTA Sec 11 refund clock with itemised proof","Preserves deposit claim but strains landlord relation"],"cost_hint":"Filing fee + lawyer consult (indicative Rs 5–15k)","time_hint":"4–12 weeks via Rent Authority (Rs 30,000/mo, residential)"},
    {"kind":"settle","title":"Negotiate itemised deductions + payment timeline","tradeoffs":["Faster refund with agreed deductions schedule","Needs written settlement to stay enforceable"],"cost_hint":"Minimal cost; 1 consult to review settlement","time_hint":"1–3 weeks of negotiation"},
    {"kind":"exit","title":"Vacate, document handover, claim via paper trail","tradeoffs":["Clean exit with photos/bills/GST + 26QC/16C trail","Gives up leverage on disputed deductions"],"cost_hint":"Moving + documentation cost only","time_hint":"Move-out week + 30-day refund clock"}
  ],
  "disclaimer": "Information, not legal advice — verify with advocate"
}
```

**Pincode hint:** `560034` → Karnataka Rent Authority phrasing via `_forum_hint` logic (mirrors `brief.py:88`).

**Invariants:**
- Never uses "sue" verb; matrix only — language at `options.py:83`.
- Costs are hints, not quotes; footer disclaimer always present.
- Maths not recomputed here; deposit/TDS numbers come from `check_deposit` / `tds_194ib` when brief calls this path.

*LLM-drafted: none — time/cost hints are deterministic strings in code, not LLM.*

**Route:** `POST /options` at `backend/app/routers/options.py:126`.

**Checklists paired:** see `examples/checklists/output.md`.
