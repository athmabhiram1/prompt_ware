# Highlight — Edge Case 2: codepoint offsets with emoji/₹

**Input:** text containing `₹` and Hindi emoji: `Rent ₹30,000 — किराया` (multi-byte UTF-8)

**Engine:** rules.py header: ``text`` is UTF-8-decoded `str`; offsets are **codepoint** indices, not bytes. `original[start:end]==excerpt` in Python `str` indexing.

**Output:** excerpt correctly slices around `₹` without cutting surrogate; start/end advance by codepoints, so highlight underline aligns 1:1 in the UI.

**Proof:** regex uses `re.IGNORECASE|DOTALL` on `str`; `_hit` at `rules.py:296` stores `text[s:e]`.

**Why edge:** byte-offset bugs would mis-highlight `₹`; codepoint invariant prevents it.
