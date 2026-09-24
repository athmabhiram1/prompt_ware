# Highlight — Abstention (no evidence to highlight)

**Input:** `samples/empty.txt` + question `Does it share data?`

**Engine:** `hybrid_search` on 1 chunk → `retrieval_confidence 0.0` (< RETRIEVAL_MIN 0.10 at `qa.py:42`) → `_abstain("NO_EVIDENCE")`.

**Output (QA):**
```json
{
  "answer": null,
  "citations": [],
  "abstain": {"reason": "The document does not contain sufficient information to answer this question. [NO_EVIDENCE]", "code": "NO_EVIDENCE"},
  "retrieval_confidence": 0.0
}
```

**Highlight policy:** zero spans rendered; UI shows proof bar with 0% and `NO_EVIDENCE` banner, not a fake highlight. Validator never runs (no claims to judge).

**Code path:** `qa.py:152` → `prompts.py:74 refuse("NO_EVIDENCE")`.
