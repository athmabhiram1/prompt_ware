# QA — Input

Source: `samples/privacy-short.md` (registered as `privacy-demo` with one page)

```
Does it share data with third parties?
```

Request:
```
POST /qa {question:"Does it share data with third parties?", doc_id:"privacy-demo", mode:"hybrid"}
```

Engine: `backend/app/routers/qa.py:210 ask_qa` → `hybrid_search` (`vec_mem.py:98`) → `answer_question` (`qa.py:144`) → CiteGuard validator (`validator.py:58`).

Thresholds: `RETRIEVAL_MIN 0.10`, `RELEVANCE_MIN 0.05`, `SUPPORT_MIN 1.0`, `MAX_REGENS 1` at `qa.py:42-45`.
