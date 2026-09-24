# Highlight — Edge Case 1: window clamping at doc start

**Input:** question about first sentence (`# Privacy Policy — QuickPay ...` at char 0)

**Engine:** `window_for(text, at=1, ...)` at `rules.py:287` clamps `start=max(0, at-LEAD)` → start 0, not negative. Excerpt still ≤WINDOW (800). `original[start:end]==excerpt` holds even at boundary.

**Output:** cite `{page:1, start:0, end:210}` with LEAD-truncated excerpt, not an out-of-bounds slice.

**Why edge:** guards `IndexError` on near-zero matches; proof line 0 remains highlightable.
