# Compare — Input

Source A: `samples/v1-lead-friendly.md`
Source B: `samples/v2-landlord-amend.md`
Premise: `residential`

Request:
```
POST /compare {a: <v1 text>, b: <v2 text>, premise:"residential"}
POST /compare/redline {same}          # → RedlinesJson
POST /compare/export.docx {same}       # → .docx
```

Engine: `backend/app/routers/compare.py:118 compare_texts` (deterministic, no LLM at request time).
