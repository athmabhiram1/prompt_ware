# Compare — Output (deterministic engine)

Ran: `compare_texts(v1, v2, premise="residential")` at `backend/app/routers/compare.py:118`.

**Result shape:** `CompareResponse` → `{a_findings, b_findings, deltas[{kind, rule_id, tier, note}], coverage}`

**Key deltas (engine-derived, abbreviated):**
```json
[
  {"kind":"risk-up","rule_id":"R01","note":"deposit: 2mo cap→10mo (excess Rs 2,40,000)"},
  {"kind":"risk-up","rule_id":"R08","note":"auto-renews for successive 2-year terms"},
  {"kind":"risk-up","rule_id":"R09","note":"may amend at any time at sole discretion without prior notice"},
  {"kind":"risk-up","rule_id":"R07","note":"entire maintenance sole responsibility"},
  {"kind":"risk-up","rule_id":"R18","note":"TDS 5% cited — outdated vs 2% since 1-Oct-2024"},
  {"kind":"deleted","rule_id":"R04","note":"overstay clause removed"},
  {"kind":"deleted","rule_id":"R16","note":"retention/deletion removed — walkaway T5"}
]
```

**Coverage:** `a: 0.52` (compliant) vs `b: 0.31` (gapped) — token-cosine overlap.

**Redline:** `POST /compare/redline` at `compare.py:349` → `RedlinesJson` (`app/engine/redline.py:47 to_redlines_json`), `POST /compare/export.docx` at `compare.py:363` → `build_redline_docx` (python-docx, `app/engine/redline.py:69`).

**Proof path:** deltas compare `scan(v1)` vs `scan(v2)` at `rules.py:369`; maths checks at `maths.py:67` for deposit cap. No LLM judge — `llm_judge()` returns literal `"clarified"` only.

**Route lines:** `compare.py:336`, `compare.py:349`, `compare.py:363` (grep-verified).

*LLM-drafted: none — delta list is deterministic engine; only the narrative heading is LLM-drafted and marked here (not an engine output).*
