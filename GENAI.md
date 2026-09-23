# GENAI.md — NyayaMitra AI Disclosure (W4.1, 2026-09-22)

Every model call site named truthfully with `file:line`. No pricing, rate-limit,
or benchmark numbers are claimed here. Anything not yet deployed is marked
`TODO-deploy`. Test counts are real pytest output from this repo.

## 1. Model inventory (all call sites)

| # | Model / function | Where | Role |
|---|-----------------|-------|------|
| 1 | `GEMINI_MODEL_NAME = "gemini-3.1-flash-lite"` | `backend/llm_provider.py:23` | Primary LLM completion via LightRAG (`gemini_model_complete`) |
| 2 | `GEMINI_EMBED_MODEL = "gemini-embedding-2-preview"`, dim from `GEMINI_EMBED_DIM` env (code default `3072`) | `backend/llm_provider.py:24-25` | Production embedding model; dim is runtime-configurable |
| 3 | `GROQ_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"`, `GROQ_BASE_URL = "https://api.groq.com/openai/v1"` | `backend/llm_provider.py:27-28` | Fallback LLM completion (provider order Gemini, Groq, Ollama) |
| 4 | `OLLAMA_EMBED_MODEL = "qwen3-embedding:8b"`, `OLLAMA_EMBED_DIM = 4096`, `DEFAULT_OLLAMA_LLM_MODEL = "qwen3.5:9b"` | `backend/llm_provider.py:30-32` | Dev-only local provider (never in prod path) |
| 5 | `get_llm_func()` | `backend/llm_provider.py:385` | Single factory returning the live LLM callable + model name |
| 6 | `get_embedding_func()` | `backend/llm_provider.py:167` | Single factory returning the live embedding callable |
| 7 | LightRAG wiring (`get_llm_func()` + `get_embedding_func()`) | `backend/lightrag_engine.py:189-190` | Only place live models enter indexing/query |
| 8 | `stub_embed()` (hashed bag-of-words, L2-normalized, `EMBED_DIM = 256`) | `backend/app/rag/vec_mem.py:32,43` | Deterministic test/dev embedding; zero keys, zero network |
| 9 | `draft_answer()` — returns `stub_answer()` on BOTH branches; live branch not implemented | `backend/app/rag/llm.py:46-52` | `LLM_LIVE=1` hook reserved for Wave 3; tests never exercise live |
| 10 | `build_prompt()` / `stub_answer()` (extractive: first sentence + true cite) | `backend/app/rag/llm.py:25,33` | Prompt assembly + offline answer path |
| 11 | `GET /demo/*` router — imports no LLM/graph/network SDK (asserted in tests) | `backend/app/routers/demo.py:1-99` | Frozen cache-only demo; never dials out by construction |

Task-routing equivalents (no separate TaskType enum exists; these are the knobs):
LightRAG `QueryParam(mode="mix", top_k=60, chunk_top_k=20, enable_rerank=true)`
in the `QA_LIGHTRAG_DEMO=1` gated path; QA `mode: hybrid|lexical|semantic`
(`backend/app/routers/qa.py:47`); Simplify `level: 5|8|10|pro` + `lang: en|hi`
(`backend/app/routers/simplify.py:147-174`).

## 2. Embedding dimensions (honest reconciliation)

Three different numbers appear in this repo; each is real in its own file:

- `backend/app/rag/vec_mem.py:6-9` — production Gemini embeddings described as
  **768d MRL-truncated**, MiniLM (`all-MiniLM-L6-v2`) **384d** fallback; tests use
  `stub_embed` at **256d** (`vec_mem.py:32`).
- `backend/llm_provider.py:25` — `GEMINI_EMBED_DIM` code default is **3072**,
  overridable via env at runtime; production Gemini embedding dim is 3072 (one truth, T1).
- `AGENTS.md:12` / `CONTEXT.md:16` — historic intent notes say **3072-dim** fixed.
  Changing the embedding dim after first index corrupts the vector store, so the
  deployed value is whatever `GEMINI_EMBED_DIM` was at index time.
  `TODO-deploy`: record the production dim in `w4.1-demo.md` at deploy time.

## 3. Prompt / validator paths

- System prompt: `CREAC_SYSTEM` — `backend/app/rag/prompts.py:15`
- Refusal template: `REFUSE_TEMPLATE` — `backend/app/rag/prompts.py:24`
- Strict-regen note: `REGEN_STRICT_NOTE` — `backend/app/rag/prompts.py:29`
- Cite protocol: `{cite:chunk_id}` markers, `protocol_errors()` — `backend/app/rag/prompts.py:35,60`
- Sentence validator (pure token math, NO LLM): Overlap >= 0.10 OR Sim >= 0.40 —
  `backend/app/rag/validator.py:16-17`, `validate_sentence()` at `validator.py:58`
- Typed refusal counters (obligation / numeric / temporal), never a single % —
  `backend/app/rag/llm.py:55-68`
- Demo bundle builder (frozen W2 engine, zero live calls) —
  `scripts/build_demo_bundles.py:1-242`

## 4. Live vs frozen behavior

- Default is cache-first: `LLM_LIVE` defaults to `0`
  (`backend/app/core/config.py:11,20,115`). Dev serves cached/preindex JSON
  without API keys.
- `/demo/*` ignores `LLM_LIVE` by design: cache always wins, `meta.llm_live`
  reports `false` (`backend/app/routers/demo.py:88-92`). Proven by
  `test_demo_live_flag_still_serves_cache` with network syscalls blocked.
- Demo bundles cost USD 0.0 per serve (`scripts/build_demo_bundles.py:135`);
  no per-call pricing is claimed anywhere in this file.

## 5. Data retention

- `/demo/*` persists nothing: bundles are read from disk
  (`data/preindex/*.json`) into an in-process `lru_cache`
  (`backend/app/routers/demo.py:60`); no user uploads, no cookies, no analytics.
- Retention duties surfaced in bundle *content* (not app storage): NDA 5-year
  retention with deletion on request, offer-letter 3-year post-exit retention
  (`scripts/build_demo_bundles.py:157-176`; DPDP Act 2023 obligations).
- API keys only via env (`GEMINI_API_KEY` / `GROQ_API_KEY`,
  `backend/app/core/config.py:118-119`); never committed.
- Paid-tier vs free-tier: use **paid-tier** Gemini/Groq keys for any real user
  data — paid tiers do not train on API data, while free-tier keys may
  retain/log inputs for abuse monitoring and training. The demo path
  (`/demo/*`, `DEMO.md`) never needs keys at all (`LLM_LIVE=0`).

## 6. Not legal advice

- Every generated brief carries a "not legal advice" line
  (asserted in `backend/tests/test_demo.py:84`).
- Statute anchors are informational: MTA Sec 11 deposit cap is
  **persuasive-only in Karnataka**; 194-IB TDS **2% since 1-Oct-2024**
  (outdated 5% cites flagged); 30-day refund clock. See bundle obligations
  (`scripts/build_demo_bundles.py:143-156`).
- Outputs help a user talk to a lawyer; they are not a lawyer.

## 7. Receipts (real, 2026-09-22)

- `pytest backend/tests/test_demo.py -q` — **8 passed**
- `pytest backend -q` — **40 passed, 2 skipped**
- `ruff check backend/app` — **clean**
- Tracked tree size — **7.0 MB across 148 files** (`git ls-files -s` +
  `git cat-file --batch-check` blob sum 7,338,484 B; limit 10 MB)
- Bundles on disk: `msa.json` 25,300 B (6 risks / 4 HIGH),
  `nda.json` 14,895 B (3 risks / 1 HIGH), `offer.json` 12,037 B (1 risk / 0 HIGH)
