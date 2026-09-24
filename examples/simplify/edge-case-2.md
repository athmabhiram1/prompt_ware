# Simplify — Edge Case 2: level pro (no grading) + 50000-char cap

**Input:** trimmed privacy policy repeated to 49,900 chars, `level:"pro", lang:"en"`

**Engine:**
- `level="pro"` → `simplify_sentence` returns single unmodified sentence per chunk (no FK reduction).
- Input cap at `simplify.py:83` `max_length=50000`; 50001 → HTTP 422.

**Outputs:**
- pro → `before.fk == after.fk` (unchanged), glossary still emitted.
- Overlong → `{"detail": "String should have at most 50000 characters"}` (pydantic).

**Proof:** capped by `Field(max_length=50000)` + `simplify_engine FK_LEVEL_TARGETS["pro"] = unchanged`. No LLM.
