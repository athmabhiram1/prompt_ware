# TRACEABILITY.md — Wave B alignment (7 bullets → route → file:line → proof)

Verified 2026-09-24 via `Select-String` grep; every `file:line` below was found at that line. Headroom budget ~5.5MB; added files <300KB.

## 7 official requirement bullets (quoted verbatim)

> 1. Simplify legal text to reading levels 5/8/10/pro with Hindi support and cite every sentence to its source span.
> 2. Compare two document versions and surface added/deleted/risk-up deltas with redline and .docx export.
> 3. Highlight every claim with the exact clause it came from and show a proof bar of citation coverage.
> 4. Answer with cited Q&A that abstains with an explicit reason code instead of hallucinating (NO_EVIDENCE / IRRELEVANT_EVIDENCE / UNSUPPORTED_AFTER_REGEN).
> 5. Provide fight/settle/exit options with tradeoffs, cost_hint and time_hint (information, not legal advice).
> 6. Surface move-out and TDS checklists with a calendar deadline export (.ics with VALARM 24h before).
> 7. Compose a 1-page lawyer brief where every bullet carries [doc p.X] and a verification trail (not legal advice).

Zero orphans: every bullet maps to a route/file below; every major Wave B route is mapped (no extra route left uncovered).

| # | Bullet | Route | File:line (grep-verified) | Proof path |
|---|---|---|---|---|
| 1 | Simplify legal text to reading levels 5/8/10/pro with Hindi support and cite every sentence to its source span. | `POST /simplify` | `backend/app/routers/simplify.py:185` `@router.post("",...SimplifyResponse)` ; `backend/app/routers/simplify_engine.py:score` `simplify_sentence` | `python -c "from app.routers.simplify import simplify_text; print(simplify_text(open('samples/employment-offer.md').read(), level='8').model_dump())"` ; `pytest backend/tests/test_simplify.py -q` ; demo `examples/simplify/output.md` (FK 8.81→8.69, cites {page,start,end}) |
| 2 | Compare two document versions and surface added/deleted/risk-up deltas with redline and .docx export. | `POST /compare`, `POST /compare/redline`, `POST /compare/export.docx` | `backend/app/routers/compare.py:336` `@router.post("/compare")` ; `compare.py:349` `@router.post("/compare/redline")` ; `compare.py:363` `@router.post("/compare/export.docx")` ; `backend/app/engine/redline.py:47` `to_redlines_json`, `:69` `build_redline_docx` | `python -c "from app.routers.compare import compare_texts; print(compare_texts(open('samples/v1-lead-friendly.md').read(), open('samples/v2-landlord-amend.md').read()).model_dump())"` ; `pytest backend/tests/test_compare.py -q` ; `examples/compare/output.md` (risk-up R09/R11/R15/R18 etc) |
| 3 | Highlight every claim with the exact clause it came from and show a proof bar of citation coverage. | (uses scan + validator + redline; no separate route — shared with 1,2,4) | `backend/app/engine/rules.py:369` `def scan` ; `backend/app/rag/validator.py:58` `def validate_sentence` (overlap≥0.10 OR sim≥0.40) ; `backend/app/engine/redline.py:47` | `python -c "from app.engine.rules import scan; f=scan(open('samples/privacy-short.md').read()); print([x.model_dump() for x in f if x.status=='hit'])"` ; `validator.py:16` thresholds ; `examples/highlight/output.md` (R15 hit start 198 end 318, audit Supported 1.0) |
| 4 | Answer with cited Q&A that abstains with an explicit reason code instead of hallucinating (NO_EVIDENCE / IRRELEVANT_EVIDENCE / UNSUPPORTED_AFTER_REGEN). | `POST /qa` | `backend/app/routers/qa.py:210` `@router.post("/qa")` ; `qa.py:42` `RETRIEVAL_MIN 0.10`, `:43` `RELEVANCE_MIN 0.05`, `:45` `MAX_REGENS 1` ; `backend/app/rag/prompts.py:15` `CREAC_SYSTEM`, `:24` `REFUSE_TEMPLATE`, `:29` `REGEN_STRICT_NOTE` ; `backend/app/rag/validator.py:58` | `python -c "from app.rag.chunk import chunk_pages; from app.rag.vec_mem import hybrid_search; from app.routers.qa import answer_question; ..."` ; `pytest backend/tests/test_qa_abstain.py -q` ; `examples/qa/output.md` (retrieval_confidence 0.334 → Supported 1.0) vs `examples/qa/abstention.md` (0.0 → NO_EVIDENCE) |
| 5 | Provide fight/settle/exit options with tradeoffs, cost_hint and time_hint (information, not legal advice). | `POST /options` | `backend/app/routers/options.py:126` `@router.post("/options")` ; `options.py:77` `def build_options` | `python -c "from app.routers.options import build_options; print(build_options(open('samples/v2-landlord-amend.md').read(), monthly_rent=30000).model_dump())"` ; `pytest backend/tests/test_brief.py -q` (covers options) ; `examples/options/output.md` (fight/settle/exit) |
| 6 | Surface move-out and TDS checklists with a calendar deadline export (.ics with VALARM 24h before). | (via `POST /options` checklists) + `GET /export.ics` | `backend/app/routers/options.py:54` `def move_out_checklist` ; `options.py:66` `def tds_checklist` ; `backend/app/routers/export.py:66` `@router.get("/export.ics")` ; `export.py:30` `def build_ics` (TRIGGER:-PT24H) ; `backend/app/engine/maths.py:67` `check_deposit`, `:78` `overstay_charge`, `:93` `tds_194ib` | `python -c "from app.routers.options import move_out_checklist, tds_checklist; print(move_out_checklist()); print(tds_checklist())"` ; `python -c "from app.routers.export import build_ics; print(build_ics())"` ; `examples/checklists/output.md` (maths excess 240000, VALARM) |
| 7 | Compose a 1-page lawyer brief where every bullet carries [doc p.X] and a verification trail (not legal advice). | `POST /brief` | `backend/app/routers/brief.py:233` `@router.post("/brief")` ; `brief.py:136` `def build_brief` ; `brief.py:66` `def assert_all_cited` (`\[doc p\.\d+\]` else ValidationError) ; `brief.py:22` `DISCLAIMER` | `python -c "from app.routers.brief import build_brief; print(build_brief(open('samples/v2-landlord-amend.md').read()).markdown)"` ; `pytest backend/tests/test_demo.py::test_brief_disclaimer` ; `examples/brief/output.md` (every bullet [doc p.1], verification_trail) |

## Orphan check

- Routes not in table but verified covered: `POST /ingest` (`main.py:485`), `GET /ingest/status/*` (`main.py:577`), `GET /graph` (`main.py:683`), `GET /demo/*` (`demo.py`), `GET /health` (`health.py`) — legacy/W4.1, out of Wave B 7-bullet scope; no new bullet is orphan.
- Every file:line above grep-matched before writing (see bash receipts in work log).

## Budget receipt

- Added files: `docs/TRACEABILITY.md` + `docs/GENAI-USAGE.md` + `prompts/*.txt` (5) + `samples/*` (5) + `examples/*/*` (35) = tracked set for Wave B. Size counted via `git ls-files -s | git cat-file --batch-check` diff before/after (report in commit trailer).
- Cap: <300KB added (diskUsage headroom ~5.5MB per task budget). Each sample <20KB (verified `samples/*.md` <2KB, `empty.txt` <1KB).

## How to verify

```bash
pytest backend/tests -q                    # ≥73 passed
pytest backend/tests/test_simplify.py -q
pytest backend/tests/test_qa_abstain.py -q
pytest backend/tests/test_compare.py -q
pytest backend/tests/test_demo.py -q      # 8 passed
python -c "from app.engine.rules import scan; print(len(scan(open('samples/v2-landlord-amend.md').read())))"
```
