# Compare — Edge Case 1: identical docs (zero deltas)

**Input:** `a = v1`, `b = v1` (same file)

**Engine:** `compare_texts(v1, v1)` → `deltas: []`, `numeric_line` none, `modal_deltas` none, coverage `1.0`.

**Output:**
```json
{"deltas": [], "coverage_a": 1.0, "coverage_b": 1.0, "note": "no material change"}
```

**Why edge:** verifies that equal token-cosine returns 1.0 without false `risk-up`. Guards regression where diff would invent additions.
