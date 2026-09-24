# QA — Output (deterministic engine at LLM_LIVE=0)

Ran: `chunk_pages("privacy-demo", [pri])` → `hybrid_search(q, chunks)` → `answer_question(q, retrieved, draft_answer)`.

**Result (engine-derived):**
```json
{
  "answer": "Synthetic short policy for ClauseCards / DPDP demo.",
  "citations": [{"page":1,"start":45,"end":1249,"span":"Synthetic short ... so R01/R04 abstain."}],
  "abstain": null,
  "audit": [{"sentence":"Synthetic short policy for ClauseCards / DPDP demo.","verdict":"Supported","overlap":1.0,"sim":0.2239}],
  "retrieval_confidence": 0.334,
  "support_ratio": 1.0,
  "regens": 0
}
```

**Guard path:**
- `retrieval_confidence 0.334` ≥ `0.10` → not `NO_EVIDENCE`.
- `draft_answer` at `backend/app/rag/llm.py:33 stub_answer` returns extractive first sentence + true cite `{cite:chunk_id}` — `LLM_LIVE=0` branch, zero network.
- `validate_sentence` at `validator.py:58` checks `overlap>=0.10 OR sim>=0.40` → `1.0` passes → `Supported` → no regen.
- Verbatim query (`QuickPay may share personal data...`) scores `0.673` with same Supported path.

**Abstain template (when triggered):** `prompts.py:24 REFUSE_TEMPLATE` → `"The document does not contain sufficient information to answer this question. [NO_EVIDENCE]"` via `prompts.refuse(code)` at `prompts.py:74`.

*LLM-drafted: the answer sentence is LLM-drafted via `stub_answer` (marked as such) but is **extractive** — verbatim slice of `chunk.text` plus correct cite; deterministic and Supported per validator. No freeform LLM generation at `LLM_LIVE=0`.*

**Route:** `POST /qa` at `backend/app/routers/qa.py:210`.

**Frontend mirror:** `frontend/src/lib/qa.ts`.
