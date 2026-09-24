# Compare — Abstention

**Input:** one side empty

```
POST /compare {a:"", b: "<v2 text>"}
```

**Engine:** `compare_texts` validates `a.strip() and b.strip()` → raises `ValueError("both sides must be non-empty")` → HTTP 422 via `compare.py:345`.

**Output:**
```json
{"detail":"both sides must be non-empty"}
```

**Policy:** never synthesizes a diff from a missing side; returns explicit 422, not a hallucinated `added/deleted` list. No LLM.

**Edge parallel:** `samples/empty.txt` vs any doc → 422.
