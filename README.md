[![CI](https://github.com/athmabhiram1/prompt_ware/actions/workflows/ci.yml/badge.svg)](https://github.com/athmabhiram1/prompt_ware/actions/workflows/ci.yml)

# NyayaMitra — Legal Document Demystifier

NyayaMitra reads hostile legal documents (rental agreements, NDAs, offer letters, Terms of Service) **for** everyday Indian users who sign papers they have never read — and shows back plain-English answers with a risk level and the exact clause each claim came from.

```bash
git clone https://github.com/athmabhiram1/prompt_ware.git
cd prompt_ware
```

Live demo:

- App: [https://prompt-ware-gray.vercel.app](https://prompt-ware-gray.vercel.app)
- API: [https://prompt-ware.onrender.com](https://prompt-ware.onrender.com)
- Offline demo (works today, zero keys): `GET /demo/priya` — see [DEMO.md](DEMO.md)

> Badge tracks the repo's real workflow (`.github/workflows/ci.yml`). If the repo is renamed in GitHub settings, the badge URL follows the rename.

## Problem

Legal documents are deliberately complex. When a Bengaluru tenant pays a ₹3,00,000 deposit on ₹30,000 rent, or an MSME signs a vendor NDA that auto-renews for successive 2-year terms, nobody reads the trap clauses: 10x deposits against a 2-month statutory cap (MTA Sec 11), unilateral amendment rights, blanket indemnities, third-party data sharing, outdated 5% TDS cites (current 2% since 1-Oct-2024). NyayaMitra scans the document with deterministic rules (R01–R18), checks the maths (deposit caps, TDS, overstay), cites every claim to a verbatim span — and says **nothing** when the paper is silent (explicit abstention with reason codes).

## Features

- **Risk scan (R01–R18):** deposit, refund, overstay, revision, tenure, maintenance, auto-renewal, amendment, termination, indemnity, liability, governing law, class waiver, data protection, retention, breach notice, TDS.
- **Exact maths (M1/M2/M3):** MTA Sec 11 deposit caps + 30-day refund clock, Sec 23 overstay multipliers, 194-IB TDS with Form 26QC/16C trail.
- **Contradictions (C1–C4):** amount mismatch, statute-understating clauses, short revision notice, outdated TDS.
- **Simplify:** reading-level grading (5/8/10/pro) + Hindi term cards, every sentence cited.
- **CiteGuard Q&A:** hybrid retrieval with explicit abstention (`NO_EVIDENCE` / `IRRELEVANT_EVIDENCE` / `UNSUPPORTED_AFTER_REGEN`).
- **Compare + redline:** version diffs with `added/deleted/risk-up` deltas and `.docx` export.
- **Lawyer brief:** 1-page cited brief + fight/settle/exit options + `.ics` deadline export. Footer on everything: *information, not legal advice*.
- **Offline demo:** `GET /demo/{priya,msme,dpdp}` serves frozen bundles with zero live calls — survives Aura-paused + Render-cold starts.

## Requirement → Feature → File

| # | Requirement | Feature | File |
|---|---|---|---|
| 1 | Upload a PDF and index it per workspace | `POST /ingest`, isolated by `company_id` | `backend/main.py:437` |
| 2 | Plain-English answers with HIGH/MEDIUM/LOW risk | `POST /query` (locked response shape) | `backend/main.py:611`, `backend/lightrag_engine.py` |
| 3 | Every claim traceable to the exact clause | `source_clauses` + `file_paths=` on insert | `backend/lightrag_engine.py`, `backend/document_loader.py` |
| 4 | Knowledge-graph view of entities | `GET /graph`, `GET /graph/subgraph` | `backend/graph_service.py`, `frontend/src/pages/KnowledgeGraph.tsx` |
| 5 | Reading-level simplify + Hindi support | `POST /simplify` (levels 5/8/10/pro, en/hi) | `backend/app/routers/simplify.py`, `frontend/src/lib/simplify.ts`, `frontend/src/components/ReadingSlider.tsx` |
| 6 | Cited Q&A that abstains instead of hallucinating | `POST /qa` (CiteGuard + regen-once) | `backend/app/routers/qa.py`, `backend/app/rag/validator.py`, `frontend/src/lib/qa.ts` |
| 7 | Offline demo + 1-page brief for the judges | `GET /demo/*` (frozen bundles) + `POST /brief` | `backend/app/routers/demo.py`, `backend/app/routers/brief.py`, `data/preindex/*.json` |
| 8 | Version compare + redline/Highlight + .docx export | `POST /compare`, `/compare/redline`, `/compare/export.docx` | `backend/app/routers/compare.py:218,229,241` |
| 9 | Clause scan with cited clause cards | Clause scan + ClauseCards/ProofBar | `backend/app/engine/rules.py`, `frontend/src/components/` |
| 10 | Fight/settle/exit options | `POST /options` (fight/settle/exit) | `backend/app/routers/options.py:118` |
| 11 | Move-out + TDS checklists + deadline export | Move-out + TDS lists + `GET /export.ics` | `backend/app/routers/options.py:118`, `backend/app/routers/export.py:60` |

## Assumptions

- Single-user demo, no auth by design (no sessions, no middleware).
- Cache-first defaults (`LLM_LIVE=0`, `LLM_PROVIDER=stub`) — no API keys required for the demo path.
- Statutes are persuasive-only; everything is information, not legal advice.
- Paid-tier API keys required only for live (non-demo) paths.
- Offline demo bundles (`data/preindex/*.json`) serve frozen results with zero live calls.

## QuickStart

Prerequisites: Python 3.12, Node 20, Docker + Docker Compose.

```bash
git clone https://github.com/athmabhiram1/prompt_ware.git
cd prompt_ware
pip install uv
uv pip install -r backend/requirements.txt
docker compose up --build
```

- Frontend: <http://localhost:3000> (dev: <http://localhost:5173> via `npm run dev` in `frontend/`)
- API: <http://localhost:8000> (dev: `uvicorn main:app --reload --port 8000` from `backend/`)
- Neo4j: <http://localhost:7474>
- Offline demo, no keys needed: `curl http://localhost:8000/demo/priya`

Env: copy `.env.example` to `.env`. Defaults are cache-first (`LLM_LIVE=0`, `LLM_PROVIDER=stub`) — no API keys required for the demo path. See [GENAI.md](GENAI.md) for model disclosure.

## Structure

```
nyayamitra/
├── backend/
│   ├── main.py                  # FastAPI app, mounts all routers (incl. W4.1 /demo)
│   ├── llm_provider.py          # ALL LLM/embedding logic (Gemini→Groq→Ollama)
│   ├── lightrag_engine.py       # LightRAG init / index / query (mode="mix")
│   ├── graph_service.py         # Neo4j graph export
│   ├── document_loader.py       # PyMuPDF PDF → clean text
│   ├── app/engine/              # R01-R18 rules, M1/M2/M3 maths, C1-C4, playbook, redline
│   ├── app/rag/                 # CiteGuard chunk/vec/prompts/llm/validator
│   ├── app/routers/             # simplify, compare, qa, brief, options, export, demo, health
│   ├── app/core/config.py       # env matrix + prod guards (LLM_LIVE=0 default)
│   └── tests/                   # pytest suite (40 passed, 2 skipped)
├── frontend/src/
│   ├── pages/                   # Home, Landing, Dashboard, Chat, KnowledgeGraph
│   ├── components/              # BriefView, DiffView, ClauseCards, ProofBar, ReadingSlider, …
│   └── lib/                     # simplify.ts, compare.ts, qa.ts, brief.ts (mirror backend schemas)
├── data/preindex/               # frozen demo bundles: msa.json (priya), nda.json (msme), offer.json (dpdp)
├── scripts/build_demo_bundles.py# offline bundle builder (W2 engine only, zero live calls)
├── DEMO.md / GENAI.md           # 3:30 demo script / model disclosure
└── docker-compose.yml           # frontend + API + Neo4j
```

## Testing

Measured 2026-09-22, `LLM_LIVE=0`, no keys (receipts in `.omo/notepads/nyayamitra/w4.1-demo.md`):

- Backend: `python -m pytest backend -q` → **40 passed, 2 skipped** (2 pre-existing skips)
- Demo gate: `python -m pytest backend/tests/test_demo.py -q` → **8 passed**, network syscalls blocked, `/demo/priya` < 2s
- Lint: `ruff check backend/app` → clean (CI also runs `ruff format --check` on owned files)
- Frontend (via CI): `npm run lint`, `npx tsc -b`, `npm test` (vitest: `simplify.test.ts`, `skeleton.test.ts`)
- No coverage % is claimed (no coverage gate configured); no latency is claimed for live paths (`to-measure-post-deploy`).

## Security

- No auth by design (single-user demo tool); no sessions, no middleware.
- Secrets via env only (`.env` never committed); TruffleHog `--only-verified` scans diffs in CI.
- `/health`, `/health/db`, `/ready` return hostnames/booleans/latencies — never secret values.
- CORS allowlist is explicit (`http://localhost:5173`, `:3000`, plus `FRONTEND_URL`); `APP_ENV=prod` refuses to boot on non-`https://` `API_URL`.
- Upload guard: `POST /ingest` accepts PDFs only (`%PDF-` magic bytes), max 10MB (`413` oversize, `422` bad-magic, `{detail}` JSON).
- Input caps: `/qa` question ≤2000 chars, `/simplify` text ≤50000, `/compare` sides ≤50000 each, `/brief` strings ≤20000 (overlong → `422`).
- Rate limit: 30 req/min/IP on `/ingest`, `/qa`, `/simplify`, `/compare`, `/brief` (slowapi, pinned in `backend/requirements.txt`).
- Logs carry `[REDACTED]` tokens, never raw doc text/entity names (`backend/app/core/redact.py`).
- Responses carry `Content-Security-Policy` + `X-Content-Type-Options: nosniff` + `X-Frame-Options: DENY` (FastAPI middleware + `vercel.json` headers).
- See [SECURITY.md](SECURITY.md).

## A11y

- CI carries an axe gate that is currently a **stub** (`.github/workflows/ci.yml:46-49` — prints `axe stub: no a11y spec yet` when `tests/a11y.spec.ts` is absent). Full `@axe-core/playwright` spec is a post-submission TODO; no a11y conformance level is claimed.

## Performance

- `GET /demo/*` serves frozen JSON from disk (in-process `lru_cache`), asserted `< 2s` offline in tests — this is the Aura-paused / Render-cold survival path.
- Cache-first defaults (`LLM_LIVE=0`, `CACHE_MODE=preindex-only`) avoid cold-start indexing; `/ready` reports bundle presence.
- Live-path latency (LightRAG query, Neo4j graph) is `to-measure-post-deploy` — not claimed here.

## License

MIT — see [LICENSE](LICENSE).
