# Highlight / CiteGuard Proof — Input

Source: `samples/privacy-short.md` line:
```
QuickPay may share personal data with third-party analytics and advertising partners for processing and marketing.
```

Question: `Does it share data with third parties?`

Engines:
- Clause scan: `backend/app/engine/rules.py:369 scan` (R15 DPA/share)
- Evidence: `backend/app/rag/vec_mem.py:98 hybrid_search` + `backend/app/rag/validator.py:58 validate_sentence`
- Redline highlight: `backend/app/engine/redline.py:47 to_redlines_json`
