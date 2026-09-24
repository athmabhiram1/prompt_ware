# QA — Edge Case 2: IRRELEVANT_EVIDENCE (low mean score)

**Input:** privacy doc + gibberish query `asdf qwer zxcv 1234` (no overlapping tokens)

**Engine:** `hybrid_search` lexical scores near 0; semantic hash also low → `relevance = mean(score) ~0.02 < RELEVANCE_MIN 0.05` at `qa.py:43` → `_abstain("IRRELEVANT_EVIDENCE")`.

**Output:**
```json
{
  "answer": null,
  "abstain": {"reason": "The retrieved evidence is not relevant to the question. [IRRELEVANT_EVIDENCE]", "code": "IRRELEVANT_EVIDENCE"},
  "retrieval_confidence": 0.08,
  "support_ratio": 0.0
}
```

**Why edge:** separates `NO_EVIDENCE` (nothing / low top-1) from `IRRELEVANT_EVIDENCE` (something but off-topic) vs `UNSUPPORTED_AFTER_REGEN` (relevant but unsupported after one regen). All three are typed refusals via `log_refusal` at `llm.py:55`.
