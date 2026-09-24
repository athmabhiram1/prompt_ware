# Highlight — Output (deterministic proof bar)

Ran: `scan(privacy-short, "residential")` + `chunk_pages + hybrid_search` + `validate_sentence`.

**Scan (R15):**
```json
{
  "rule_id":"R15",
  "clause":"data_protection",
  "status":"hit",
  "tier":4,
  "note":"data sharing with third parties",
  "excerpt":"may share personal data with third-party analytics and advertising partners for processing and marketing.",
  "start": 198,
  "end": 318
}
```
Invariant: `original[198:318] == excerpt` (rules.py head comment). Window ≤800 chars (`WINDOW=800, LEAD=200` at rules.py:18).

**CiteGuard proof bar (deterministic, no LLM):**
- Retrieval: `hybrid_search` lexical+semantic → `retrieval_confidence 0.334` for Q2, `0.673` for verbatim excerpt (see engine dump).
- Validator: `validate_sentence(claim, chunk.text)` → `overlap 1.0, sim 0.22` → `Supported` (`validator.py:16` `overlap>=0.10 OR sim>=0.40`).
- Audit row: `{sentence:"Synthetic short policy...", verdict:"Supported", overlap:1.0, sim:0.2239}` — `backend/app/routers/qa.py:118`.

**Highlight rendering:**
- ClauseCards badge: `R15 T4` + span highlight via `frontend/src/components/ClauseCards`.
- Redline: `to_redlines_json` marks same window as `risk-up` when comparing to DPA-clean variant.
- `ProofBar` shows 100% citation coverage.

*LLM-drafted: none — overlap/sim numbers above are deterministic `validator.py` output.*

**File:lines:** `rules.py:369`, `validator.py:58`, `vec_mem.py:98`, `redline.py:47`, router `qa.py:210`.
