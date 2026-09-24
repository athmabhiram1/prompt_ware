# Simplify — Edge Case 1: level 5 + Hindi brackets

**Input:** same employment offer, `level:"5", lang:"hi"`

**Engine:** `simplify_sentence(..., level="5")` splits long sentences (max_words per FK target) + `to_hindi_sentence` wraps with `<hi> (<en>)` brackets.

**Output (first 2 cites, deterministic):**
- `Candidate — Aarav Mehta (उम्मीदवार (Candidate))`
- `Data is kept for 3 years after exit.` → `डेटा 3 साल तक रखा जाता है (Data is kept for 3 years) [page 1]`

**Invariant:** Hindi still carries source span; `hindi_with_bracket` at `simplify_engine.py`. FK target for 5 → ≤6.0. Verified via `score()` before/after delta.

**Why edge:** tests FK recalc + bracket rendering + `ReadingSlider.tsx` live region.
