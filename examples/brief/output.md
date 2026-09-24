# Brief — Output (deterministic engine)

Ran: `build_brief(v2_text, premise="residential", pincode="560034", job_id="brief")` at `backend/app/routers/brief.py:136`.

**Markdown (engine-derived, cites required via `assert_all_cited` at brief.py:66):**

```markdown
# NyayaMitra — Lawyer Brief (1 page)

> Information, not legal advice — verify with advocate

## Facts
- Agreement excerpt reviewed (18 clauses scanned, premise residential) [doc p.1]
- Plain-language gist: This sample is synthetic and short... [doc p.1]

## Risks
- R09 unilateral_amendment tier T4 — flagged [doc p.1]
- R11 indemnity tier T4 — flagged [doc p.1]
- R15 data_protection tier T4 — flagged [doc p.1]
- R01 deposit tier T4 — flagged [doc p.1]
- R18 tds tier T3 — flagged [doc p.1]
- R08 auto_renewal tier T3 — flagged [doc p.1]
- R07 maintenance tier T2 — flagged [doc p.1]
- R10 termination tier T3 — flagged [doc p.1]

## Missing
- R06 tenure missing — verify before signing [doc p.1]
- R16 retention missing — verify before signing [doc p.1]

## Deadlines
- Deposit refund within one month of vacant possession with itemised statement (MTA Sec 11) [doc p.1]
- Overstay compensation 2x first 60 days then 4x (MTA Sec 23) [doc p.1]
- TDS 2% on rent > Rs 50,000/mo since 1-Oct-2024; Form 26QC within 30 days + Form 16C, no TAN (Sec 194-IB) [doc p.1]

## Questions for lawyer
- Is the deposit within MTA Sec 11 caps for this premise? [doc p.1]
- Does the refund/overstay/TDS trail (26QC/16C) match the agreement dates? [doc p.1]
- Forum check: Karnataka Rent Authority (MTA) — ask lawyer if Rent Authority vs civil court fits your pincode [doc p.1]
```

**Verification trail (engine at brief.py:213):**
```json
[{"source":"R01","section":"Risks","timestamp":"2026-09-23T...Z"}, ...]
```

**Cites:** `cites[]` at `brief.py:108` — each `BriefCite` reuses `finding.excerpt` with `page:1, start:end`, no invented cite. `original[start:end]==excerpt` invariant from `rules.py`.

**Invariants:**
- Every bullet matches `\[doc p\.\d+\]` else `ValidationError` at `brief.py:66`.
- `redline_docx_path: "redline-brief.docx"` at `brief.py:225` (deterministic path, bytes via `redline.build_redline_docx`).
- Disclaimer footer `DISCLAIMER` at `brief.py:22` on every brief (asserted in `test_demo.py:84`).

*LLM-drafted: the two "Facts" bullets' plain gist (`simp.sentences[0].text`) is LLM-adjacent via `simplify_text` deterministic core — extractive, cited; no freeform LLM. Marked as deterministic per `GENAI-USAGE.md`.*

**Routes verified:** `brief.py:233`, `rules.py:369`, `simplify.py:118`, `export.py:66` (`.ics` companion).
