# Options — Abstention / Neutral Handling

**Input:** `samples/empty.txt` + `monthly_rent=0`

**Engine:** `build_options(empty, monthly_rent=0)` does not raise — it returns the same 3-option matrix with `rent_bit="stated rent"` at `options.py:85`.

**Policy:** options is a **matrix**, not a fact answer — there is nothing to abstain on for missing doc text; the engine degrades to neutral rent text rather than inventing a deposit breach. True abstention lives in QA (`NO_EVIDENCE`), not here.

**Output:**
```json
{"options": [/* fight/settle/exit neutral */], "move_out_checklist": [...], "tds_checklist": [...], "disclaimer": "Information, not legal advice — verify with advocate"}
```

**If truly empty:** caller should route through QA/brief gates instead; options will still return a usable checklist without fabricating facts.

*LLM-drafted: none.*
