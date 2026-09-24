# GENAI-USAGE.md — NyayaMitra GenAI disclosure (Wave B)

Budget: this file < 10KB; prompts/ total < 50KB. Detects at GENAI.md inventory.

## 1. Models (see GENAI.md one-truth)

| Model | Where | Role |
|---|---|---|
| `gemini-3.1-flash-lite` | `backend/llm_provider.py:23` | Primary LLM via `get_llm_func()` |
| `gemini-embedding-2-preview` (dim `GEMINI_EMBED_DIM` default 3072) | `backend/llm_provider.py:24-25` | Embedding |
| `meta-llama/llama-4-scout-17b-16e-instruct` | `backend/llm_provider.py:27` | Fallback |
| `stub_embed` (256d hashed BoW) | `backend/app/rag/vec_mem.py:32,43` | Deterministic test/dev |
| `draft_answer → stub_answer` | `backend/app/rag/llm.py:46` | Offline extractive answer (LLM_LIVE=0) |

Live entry only via `backend/lightrag_engine.py:189-190`. `GET /demo/*` imports no LLM (`backend/app/routers/demo.py:1-99`).

## 2. Where AI vs deterministic (exact boundary)

**Deterministic (no LLM, no network):**
- R01-R18 scan `backend/app/engine/rules.py:369 scan` (regex, WINDOW 800, LEAD 200)
- Maths M1/M2/M3 `backend/app/engine/maths.py:67,78,93` (deposit cap, overstay, TDS 2%)
- Contradictions C1-C4 `backend/app/engine/contradict.py:128 detect`
- Playbook verdict `backend/app/engine/playbook.py:111 verdict`
- Simplify grading `backend/app/routers/simplify_engine.py:score`, `simplify_sentence` (FK/FRE math)
- QA retriever `backend/app/rag/vec_mem.py:98 hybrid_search` + validator `backend/app/rag/validator.py:58 validate_sentence` (overlap ≥0.10 OR sim ≥0.40)
- Compare deltas `backend/app/routers/compare.py:118 compare_texts`, redline `backend/app/engine/redline.py:47`
- Options matrix + checklists `backend/app/routers/options.py:54,66,77`
- Brief composition `backend/app/routers/brief.py:136 build_brief` + cite guard `brief.py:66 assert_all_cited`
- ICS `backend/app/routers/export.py:30 build_ics`

**AI-assisted (LLM-drafted, marked):**
- QA answer sentence when `LLM_LIVE=0` — `stub_answer` is *extractive* first sentence + true cite (deterministic stand-in, marked `LLM-drafted (stub)` in examples/qa/output.md)
- Brief plain gist (`simp.sentences[0].text`) and 3 lawyer questions phrasing — extractive/canned, each forced to end `[doc p.X]` and validated.

**Guards (never bypassed):**
- `LLM_LIVE` defaults `0` (`backend/app/core/config.py:11,20`), `/demo` ignores it (`demo.py:88-92`)
- `assert_all_cited` rejects uncited bullets (`brief.py:66`), `protocol_errors` rejects bad `{cite:*}` (`prompts.py:60`), `validate_sentence` rejects unsupported claims.
- Input caps: `/qa` question ≤2000 (`qa.py:51`), `/simplify` ≤50000 (`simplify.py:83`), `/compare` sides ≤50000, `/brief` ≤20000, `/options` ≤20000 — paginated by Pydantic Field, not LLM.
- Rate limit 30/min/IP on ingest/qa/simplify/compare/brief (`backend/app/core/limits.py`, slowapi).

## 3. Prompt inventory (raw files)

| File | Covers | Entry |
|---|---|---|
| `prompts/simplify.txt` | FK/FRE grading + Hindi brackets | `simplify_engine.py:score`, `simplify.py:118` |
| `prompts/qa.txt` | CREAC + REFUSE_TEMPLATE + REGEN_STRICT_NOTE + validator thresholds | `prompts.py:15,24,29`, `validator.py:16`, `qa.py:42-45` |
| `prompts/brief.txt` | 1-page sections + assert_all_cited | `brief.py:66,136` |
| `prompts/compare.txt` | token_cosine + scan deltas + redline | `compare.py:118`, `redline.py:47,69` |
| `prompts/options.txt` | fight/settle/exit matrix + checklists | `options.py:54,66,77` |

Each prompt file is the verbatim system/user text plus deterministic tail — no secrets, no keys.

## 4. Not legal advice

Every brief/options/ics carries `Information, not legal advice — verify with advocate` at `brief.py:22`, `options.py:17`, `export.py:14` + disclaimer in every example. Statutes persuasive-only: MTA caps 2mo/6mo, refund 30d (Sec 11), overstay 2x/4x (Sec 23), 194-IB 2% since 1-Oct-2024, 26QC/16C no TAN.
