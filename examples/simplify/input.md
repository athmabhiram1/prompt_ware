# Simplify — Input

Source: `samples/employment-offer.md` (excerpt)

```
Candidate: Aarav Mehta, Software Engineer, Delhi.
Monthly CTC Rs 78,000. Monthly rent allowance Rs 22,000.
Data retained for 3 years post-exit, deletion on request.
Personal data shall not be shared with third parties without consent; breach notification within 72 hours.
Company may terminate with immediate effect for cause; employee with 30 days notice.
Auto-renews for successive 1-year terms unless 30 days notice.
TDS will be deducted at 5% under Section 194-IB on rent payments.
```

Request: `POST /simplify {text, level:"8", lang:"en"}`

Engine: `backend/app/routers/simplify.py:118 simplify_text` → `backend/app/routers/simplify_engine.py:score`.
