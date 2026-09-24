# Compare — Edge Case 2: overlong side (50000 cap)

**Input:** `a` = 50,001 chars (repeat privacy policy), `b` = v2

**Engine:** `CompareRequest` at `compare.py` has `Field(max_length=50000)` on both sides → Pydantic 422 before engine runs.

**Output:**
```json
{"detail":[{"loc":["body","a"],"msg":"String should have at most 50000 characters","type":"string_too_long"}]}
```

**Proof:** capped at router schema; `LIMITS RATE_30_PER_MIN` also applies. No engine invoked, no LLM.
