# Project Context — Legal Document Demystifier

## What We Are Building
A local-first, demo-ready web application that takes complex legal documents (Terms of Service, privacy policies, rental agreements) and makes them understandable to everyday users. The user uploads a PDF, asks questions in plain English, and gets back a clear answer with a risk level (HIGH / MEDIUM / LOW) and the exact clause it came from.

## The Core Problem
Legal documents are deliberately complex. When an Indian user signs up for Truecaller, Zomato, or PhonePe, they agree to terms they have never read. This tool reads those documents for them and answers specific questions like "does this app share my contacts?" or "can I dispute a charge?"

## Tech Stack (Locked — Do Not Suggest Alternatives)
- **RAG Engine**: LightRAG (`lightrag-hku` pip package) with `mode="mix"`
- **Graph DB**: Neo4j (local, Desktop edition) via `Neo4JStorage`
- **Vector DB**: NanoVectorDBStorage (LightRAG default, file-based)
- **LLM — Primary**: Groq API (`llama-3.3-70b-versatile`)
- **LLM — Fallback**: Google Gemini API (`gemini-2.0-flash`)
- **LLM — Last Resort**: Ollama (local, only if both APIs fail)
- **Embeddings**: Gemini (`gemini-embedding-2-preview`, 3072-dim) — FIXED, never change after first index. Set `EMBED_PROVIDER=ollama` (`qwen3-embedding:0.6b`, 1024-dim) only if Gemini is unavailable; delete `rag_storage/` before switching providers.
- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: React + TypeScript + Vite + Tailwind + Zustand
- **Graph Viz**: `react-force-graph-2d`
- **PDF Parsing**: PyMuPDF (`fitz`)

## Folder Structure
```
project/
├── backend/
│   ├── main.py                  # FastAPI app, mounts all routers
│   ├── llm_provider.py          # ALL LLM/embedding provider logic lives here
│   ├── lightrag_engine.py       # LightRAG init, index_document(), query()
│   ├── graph_service.py         # Direct Neo4j queries for graph export
│   ├── document_loader.py       # PyMuPDF PDF → clean text
│   ├── index_documents.py       # One-time script to pre-index documents/
│   ├── documents/               # Pre-downloaded Indian ToS PDFs live here
│   └── .env                     # API keys and config — never commit this
└── frontend/
    └── src/
        ├── App.tsx
        ├── pages/
        │   ├── Upload.tsx        # Screen 1: upload + indexing status
        │   ├── Chat.tsx          # Screen 2: query + risk badges + citations
        │   └── GraphView.tsx     # Screen 3: force-graph visualization
        ├── components/
        │   ├── RiskBadge.tsx
        │   ├── SourceClause.tsx
        │   └── ForceGraph.tsx
        └── store/
            └── useAppStore.ts    # Zustand global state
```

## API Contract (Locked — Frontend and Backend Must Agree on This)

### POST /ingest
- Input: `multipart/form-data` with a PDF file
- Returns immediately: `{"status": "indexing", "doc_id": "<filename>"}`
- Indexing runs as a FastAPI BackgroundTask

### GET /ingest/status/{doc_id}
- Returns: `{"doc_id": "...", "status": "indexing" | "ready" | "failed"}`

### POST /query
```json
// Request
{ "question": "Does Truecaller share my contacts?", "doc_filter": null }

// Response — shape is LOCKED
{
  "answer": "Yes, Truecaller shares your contacts...",
  "risk_level": "HIGH",
  "source_clauses": [
    { "file": "truecaller_tos.pdf", "excerpt": "We may share your data with partners..." }
  ],
  "graph_nodes_involved": ["data_sharing", "third_party", "contacts"]
}
```

### GET /graph
- Returns all nodes + edges (capped at 300 nodes)
- Shape: `{ "nodes": [...], "edges": [...], "stats": { "node_count": n, "edge_count": m } }`

### GET /graph/subgraph
- Query param: `?nodes=data_sharing,third_party`
- Returns subgraph of those nodes + their 1-hop neighbors

## Key Constraints
1. **No auth** — single-user demo tool, no login
2. **Local only** — everything runs on one laptop, no cloud deployment
3. **PDF only** — no other document formats
4. **Embedding model is immutable** — once the first document is indexed with Gemini embeddings, every subsequent document and every query must use the same model. Changing it requires deleting all vector data and re-indexing everything.
5. **Citations are enabled via `file_paths=` at insert time** — every `rag.insert()` call must pass `file_paths=[...]` or source attribution breaks
6. **Risk level comes from the LLM** — assigned via `QueryParam(user_prompt=...)` instruction, parsed from LLM response. No separate classifier.

## Pre-Indexed Documents (in backend/documents/)
Truecaller, PhonePe, Paytm, Zomato, Swiggy, CRED, Instagram, Google, Ola, IRCTC — all Terms of Service / Privacy Policy PDFs downloaded manually.

## What "Done" Looks Like
A judge sits down, uploads the Truecaller ToS, asks "does this app share my contacts with advertisers?", and sees a red HIGH RISK badge, a plain-English answer, and the exact clause highlighted. They switch to the Graph tab and see the knowledge graph with the relevant nodes glowing gold.