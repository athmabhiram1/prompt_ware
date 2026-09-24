# Checklists — Edge Case 2: rent exactly at TDS threshold

**Input:** `monthly_rent=50000` (threshold at `maths.py:23 TDS_THRESHOLD=50000`)

**Engine:** `tds_194ib(50000,12)` at `maths.py:93` → `applicable: false` (condition is `rent > 50000`, not `>=`). `yearly_tds 0.0`.

**Output:** TDS checklist still emitted (procedure), but maths result shows not applicable. Brief task routes this correctly: `2% on rent > Rs 50,000/mo (not applicable here)` wording.

**Why edge:** prevents off-by-one filing advice at threshold.
