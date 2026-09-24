# Options — Input

Source: `samples/v2-landlord-amend.md` (trap-laden amendment)
Params: `monthly_rent=30000, premise="residential", pincode="560034"`

Request:
```
POST /options {text: <v2 text>, monthly_rent:30000, premise:"residential", pincode:"560034"}
```

Engine: `backend/app/routers/options.py:77 build_options` (deterministic matrix, no LLM).

Statutes baked into text: MTA Sec 11 (2mo cap), Sec 23 (2x/4x overstay), 194-IB 2% since 1-Oct-2024 — `options.py:3-6`.
