# Checklists — Edge Case 1: date edge (dtstart variant)

**Input:** `GET /export.ics?dtstart=20260430T100000` vs `GET /export.ics?dtstart=` (empty)

**Engine:** `build_ics` at `export.py:30` — empty `dtstart` falls to `_DEFAULT_DTSTART="20260430T100000"`; `dtend` defaults to `start[:8]+"T110000"` (one hour). `_clean` caps title at 200 chars.

**Output:** `DTSTART:20260430T100000` / `DTEND:20260430T110000` + `TRIGGER:-PT24H` (tested in `gen_examples.json` with `20260501T100000`).

**Why edge:** guards empty query param + ensures VALARM 24h before still resolves in Google Calendar.
