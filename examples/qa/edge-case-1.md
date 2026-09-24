# QA — Edge Case 1: overlong question (2000 cap)

**Input:** question of 2,001 chars (repeat of demo question)

**Engine:** `QaRequest` at `qa.py:51` has `Field(max_length=2000)` on `question` → Pydantic 422 before retrieval.

**Output:**
```json
{"detail":[{"loc":["body","question"],"msg":"String should have at most 2000 characters","type":"string_too_long"}]}
```

**Guard:** input cap at `main.py` + `qa.py` + `limits.py:RATE_30_PER_MIN`. No engine, no LLM.

**Why edge:** tests client-side truncation vs server 422 path.
