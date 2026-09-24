# Brief — Edge Case 2: pincode 11xxxx → Delhi forum hint

**Input:** `build_brief(v2, pincode="110001")`

**Engine:** `_forum_hint` at `brief.py:87-93` → `pin.startswith("56")` → Karnataka; `pin.startswith("11")` → `Delhi Rent Authority — ask lawyer if Rent Authority vs civil court fits your pincode`.

**Output (Questions line 3):**
```
- Forum check: Delhi Rent Authority — ask lawyer if Rent Authority vs civil court fits your pincode [doc p.1]
```

**Neutral pin (`400001`)** → `"Rent Authority vs civil court vs consumer forum — ask lawyer which forum fits your pincode"`.

**Why edge:** guards hardcoded-Bengaluru bias; pincode drives forum suggestion, disclaimer stays.

*LLM-drafted: forum hint strings are deterministic per pincode prefix, not LLM.*
