# Options — Edge Case 2: overlong source (20000 cap)

**Input:** `text` of 20,001 chars

**Engine:** `OptionsRequest` at `options.py:27` has `max_length=20000` on `text`/`job_id`/`doc_id` → Pydantic 422 before `build_options`.

**Output:**
```json
{"detail":[{"loc":["body","text"],"msg":"String should have at most 20000 characters","type":"string_too_long"}]}
```

**Proof:** capped at router schema; rate limit `RATE_30_PER_MIN` also applies. No LLM.
