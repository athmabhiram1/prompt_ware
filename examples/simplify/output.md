# Simplify — Output (deterministic engine)

Source: run `python -c "from app.routers.simplify import simplify_text; ..."` at `LLM_LIVE=0`.

```json
{
  "before": {"fk": 8.81, "fre": 50.64},
  "after": {"fk": 8.69, "fre": 51.48},
  "level": "8",
  "lang": "en"
}
```

**Cited sentences (first 3, verbatim spans, `text[start:end]==excerpt`):**

1. `# Employment Offer — PixelWorks Pvt Ltd (Sample, <20KB) This sample is synthetic and short for offline demo only.` — cite `{page:1, start:0, end:114}`
2. `Not legal advice.` — cite `{page:1, start:115, end:132}`
3. `**Candidate:** Aarav Mehta, Software Engineer, Delhi.` — cite `{page:1, start:133, end:186}`

**Glossary (deterministic, `simplify_engine.py:extract_glossary`):**
- `rent` — Money the tenant pays to use the property. (hi: किराए)
- `consent` — Permission given for a specific use. (hi: सहमति)
- `termination` — Ending the contract before its full term. (hi: समाप्ति)
- `notice` — A written warning sent before further action. (hi: नोटिस)

**Proof:** every sentence carries `{page,start,end}`; `end>start` validated at `simplify.py:53`. No sentence invented — each reuses source span. Graded parts rated FK ≤8.5 per `level=8` target.

**Route:** `POST /simplify` at `backend/app/routers/simplify.py:185` (schema frozen for brief).

*LLM-drafted: none in this output — all values are deterministic engine at `simplify_engine.py:score`.*
