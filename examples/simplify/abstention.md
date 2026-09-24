# Simplify — Abstention / Refusal

**Input:** `samples/empty.txt` (or empty string)

```
EMPTY — Contains no clauses, no amounts, no dates.
```

**Engine:** `simplify_text("", level="8")` at `backend/app/routers/simplify.py:121`

```python
raise ValueError("text must not be empty")
# → HTTP 422 via simplify.py:196
```

**Output:**

```json
{"detail": "text must not be empty"}
```

**Policy:** deterministic — no hallucinated simplification, no invented cite. Frontend shows validation error, not a fake grade. No LLM call.

**Test:** `pytest backend/tests/test_simplify.py -q` covers empty + overlong (50000) guards.
