# QA — Abstention

**Input:** `samples/empty.txt` (registered `empty-demo`) + question `What is the monthly maintenance charge?`

**Engine:** `hybrid_search` on 1 chunk → score `0.0` → `retrieval_confidence 0.0 < 0.10` at `qa.py:42` → `_abstain("NO_EVIDENCE", "true", ...)`.

**Output (engine-derived):**
```json
{
  "answer": null,
  "citations": [],
  "abstain": {"reason": "The document does not contain sufficient information to answer this question. [NO_EVIDENCE]", "code": "NO_EVIDENCE"},
  "audit": [],
  "retrieval_confidence": 0.0,
  "support_ratio": 0.0,
  "regens": 0
}
```

**Other codes (explicit at qa.py:10-16):**
- `IRRELEVANT_EVIDENCE` when `relevance (mean score) < 0.05` (true refusal).
- `UNSUPPORTED_AFTER_REGEN` when `support_ratio < 1.0` after one regen (false refusal — evidence existed but unusable; strict note at `prompts.py:29 REGEN_STRICT_NOTE`).

**UI:** shows abstain banner with code, zero cites invented. Tracked in `DEMO.md` abstain beat.

**Proof:** `qa.py:152-156`, `prompts.py:74`, `validator.py:58` thresholds are deterministic, not LLM.
