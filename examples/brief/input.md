# Brief — Input

Source: `samples/v2-landlord-amend.md` (trap-laden amendment)
Params: `premise="residential", pincode="560034", job_id="brief"`

Request:
```
POST /brief {text: <v2 text>, premise:"residential", pincode:"560034", job_id:"brief"}
```

Engine: `backend/app/routers/brief.py:136 build_brief` — composes **only frozen W2 schemas**:
- `Finding` from `app/engine/rules.py:369 scan`
- `ReadScores` from `app/routers/simplify.py:148 simplify_text`
- No live LLM; `assert_all_cited` at `brief.py:66` guards every bullet.

Route: `POST /brief` at `brief.py:233`.
