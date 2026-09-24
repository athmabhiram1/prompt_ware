# Options — Edge Case 1: zero rent (deposit calc guard)

**Input:** `text=v2`, `monthly_rent=0`

**Engine:** `check_deposit(300000, 0)` at `maths.py:67` → `cap_amount=0`, `excess=300000`, `breach=True` — still deterministic. Options `rent_bit` falls to `"stated rent"` (`options.py:85`) rather than dividing by zero.

**Output:** time_hint `"4–12 weeks via Rent Authority (stated rent, residential)"` — no crash, no NaN.

**Why edge:** guards `monthly_rent=0` before any `daily_rent = rent/30` in overstay path.
