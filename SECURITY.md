# Security Policy
Report vulnerabilities via GitHub Security Advisories (private) — do not open public issues.
We run `trufflehog --only-verified` on every PR and `npm audit` / `pip-audit` before releases.
Secrets in history are purged with git-filter-repo and rotated immediately (see W1.1).
Day-1 skeleton: no bug-bounty; fixes land as patch releases with credit in release notes.

## Request limits (F2 hardening)

- `POST /ingest`: PDF only, enforced by `%PDF-` magic bytes (not just
  `content_type`); max `10*1024*1024` bytes via Content-Length pre-check plus
  post-read `len()` check. Oversize → `413`, bad magic → `422`,
  empty/wrong-type → `400`. All errors keep the JSON `{detail}` shape.
- Body caps (overlong → `422` via Pydantic `max_length`): `/qa` question
  ≤2000, `/simplify` text ≤50000, `/compare` sides ≤50000 each,
  `/brief` strings ≤20000, `/query` question ≤2000.
- Rate limit: 30 requests/minute/IP on `/ingest`, `/qa`, `/simplify`,
  `/compare`, `/brief` via slowapi (`slowapi==0.1.10` pinned).
- PII: `backend/app/core/redact.py::redact_pii` masks PAN-like, digit-run,
  email-like, and phone-like tokens and truncates long excerpts; all
  `logger.*` calls carrying doc text/IDs (`main.py`, `graph_service.py`,
  `lightrag_engine.py`) log `[REDACTED]` forms only.
- Headers: every API response carries `Content-Security-Policy`
  (`default-src 'self'; frame-ancestors 'none'; object-src 'none'`),
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`; `vercel.json` sets the same on the frontend.
