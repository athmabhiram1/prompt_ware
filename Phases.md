# Project Phase Plan — Legal Document Demystifier

---

## Guiding Principles
- **Occam's Razor**: Every component must justify its existence. No speculative features.
- **Vertical slices**: Each phase produces something runnable end-to-end, not just a layer.
- **Gate discipline**: Do not start the next phase until the exit criteria of the current one are met.
- **Mixed team**: Phases are designed so two people can work in parallel from Phase 2 onward.

---

## Phase 0 — Environment & Skeleton
**Goal**: Every team member can run the same thing. Nothing breaks on anyone's machine.  
**Parallel work**: All three together. Do this in one sitting.

### Tasks
- [ ] Create monorepo: `backend/` and `frontend/` folders, one root `README.md`
- [ ] Backend: Python 3.11+ virtual env, install `lightrag-hku[api]`, `fastapi`, `uvicorn`, `pymupdf`, `python-dotenv`
- [ ] Frontend: `npm create vite@latest frontend -- --template react-ts`, install `tailwindcss`, `zustand`, `axios`
- [ ] Create `.env` with all keys as empty placeholders:
  ```
  GROQ_API_KEY=
  GEMINI_API_KEY=
  NEO4J_URI=neo4j://localhost:7687
  NEO4J_USERNAME=neo4j
  NEO4J_PASSWORD=
  NEO4J_DATABASE=neo4j
  OLLAMA_BASE_URL=http://localhost:11434
  PRIMARY_LLM_PROVIDER=groq        # groq | gemini | ollama
  ```
- [ ] Install Neo4j Desktop locally, create a database, confirm browser at `localhost:7474`
- [ ] Install Ollama, pull `nomic-embed-text`: `ollama pull nomic-embed-text`
- [ ] Verify Groq API key works (free tier, no card needed at console.groq.com)
- [ ] Verify Gemini API key works (aistudio.google.com)
- [ ] Backend: `python -c "from lightrag import LightRAG; print('ok')"` — must pass
- [ ] Frontend: `npm run dev` — must render Vite default page

### Exit Criteria
All three team members run backend and frontend with no import errors. Neo4j browser loads. Ollama serves embeddings.

---

## Phase 1 — LightRAG Core + LLM Fallback Chain
**Goal**: A working Python script that indexes one PDF and answers one question. No API, no UI yet.  
**Owner**: 1–2 people (backend/ML focused)

### Tasks

#### 1A — LLM Provider Abstraction
Build `backend/llm_provider.py` — a single async function `get_llm_func()` that tries providers in order:

```
Primary:   Groq  (llama-3.3-70b)
Fallback:  Gemini (gemini-2.0-flash)
Last resort: Ollama (whatever 32B+ model is available locally)
```

The function reads `PRIMARY_LLM_PROVIDER` from `.env` and returns the appropriate LightRAG-compatible async callable. This is the only place provider logic lives. Every other file imports from here.

**Important**: Use Gemini's embedding (`models/text-embedding-004`, 768-dim) as the single embedding model, NOT Ollama. Reason: Gemini embed is free, multilingual, and handles Indian legal text better than `nomic-embed-text`. Ollama embed stays as a documented fallback only.

#### 1B — LightRAG Engine
Build `backend/lightrag_engine.py`:
- Init LightRAG with `Neo4JStorage` for graph, `NanoVectorDBStorage` for vectors
- Use `file_paths=` parameter on every `rag.insert()` call — this is what enables source citations
- Expose two async functions: `index_document(pdf_path: str)` and `query(question: str) -> dict`
- The `query` function must call `rag.aquery()` with `mode="mix"` and `QueryParam(only_need_context=False)`

#### 1C — PDF Loader
Build `backend/document_loader.py`:
- Use `pymupdf` (`fitz`) to extract text from PDF
- Strip headers/footers heuristically (lines under 50 chars at top/bottom of page)
- Return clean string + metadata (filename, page count)

#### 1D — Smoke Test Script
`backend/smoke_test.py` — not a unit test, just a script:
```
1. Load one ToS PDF (e.g., Truecaller)
2. Index it via lightrag_engine.index_document()
3. Query: "Does Truecaller share my contacts with third parties?"
4. Print raw LightRAG output to terminal
5. Confirm Neo4j browser shows nodes
```

### Exit Criteria
- Smoke test runs without errors
- LightRAG returns an answer string (quality doesn't matter yet)
- Neo4j browser at `localhost:7474` shows at least 20 nodes after indexing
- Source file name appears somewhere in the raw output (confirms citations wired up)
- If Groq is rate-limited, manually set `PRIMARY_LLM_PROVIDER=gemini` and rerun — must still work

---

## Phase 2 — FastAPI Backend (3 Endpoints)
**Goal**: The backend is a real HTTP server. Frontend can talk to it.  
**Parallel work**: Person A builds the API. Person B starts Phase 3 (frontend scaffold) simultaneously.

### Tasks

#### Endpoint 1: `POST /ingest`
- Accepts: `multipart/form-data` with a PDF file
- Calls `document_loader.py` → `lightrag_engine.index_document()`
- Indexing is slow (2–5 min). Run it in a `BackgroundTask`
- Returns immediately: `{"status": "indexing", "doc_id": "<filename>", "message": "Indexing started"}`
- Maintain a simple in-memory dict `indexing_status: dict[str, str]` with states: `indexing | ready | failed`

#### Endpoint 2: `GET /ingest/status/{doc_id}`
- Returns current status from `indexing_status` dict
- Frontend polls this every 3 seconds after upload

#### Endpoint 3: `POST /query`
Request body:
```json
{
  "question": "Does Truecaller share my contacts?",
  "doc_filter": null
}
```
Response — **this shape is locked, frontend depends on it**:
```json
{
  "answer": "Yes, Truecaller shares...",
  "risk_level": "HIGH",
  "source_clauses": [
    {
      "file": "truecaller_tos.pdf",
      "excerpt": "We may share your data with partners..."
    }
  ],
  "graph_nodes_involved": ["data_sharing", "third_party", "contacts"]
}
```

**How risk_level is assigned**: Instruct the LLM via `QueryParam(user_prompt=...)` to append a JSON block at the end of its response containing `risk_level` (HIGH/MEDIUM/LOW) and `graph_nodes_involved`. Parse this block in `lightrag_engine.py`. If parsing fails, default to `risk_level: "UNKNOWN"`. Do not build a separate classifier.

#### Endpoint 4: `GET /graph`
- Query Neo4j directly (not through LightRAG) for all nodes and edges
- Return:
```json
{
  "nodes": [{"id": "data_sharing", "label": "data_sharing", "type": "entity"}],
  "edges": [{"source": "data_sharing", "target": "third_party", "label": "shared_with"}],
  "stats": {"node_count": 147, "edge_count": 203}
}
```
- Cap at 300 nodes for performance — use `LIMIT 300` in the Cypher query

#### Endpoint 5: `GET /graph/subgraph/{query_id}`
- Accepts a query string param `?nodes=data_sharing,third_party,contacts`
- Returns the subgraph for only those nodes + their 1-hop neighbors
- This is what highlights relevant nodes after a query

#### CORS
Enable CORS for `localhost:5173` (Vite dev server).

### Exit Criteria
- All endpoints return correct shapes via `curl` or Postman
- Upload a PDF → poll status → get `ready` → query → get structured JSON response
- `/graph` returns nodes and edges visible in Neo4j
- Groq → Gemini fallback tested by temporarily invalidating the Groq key

---

## Phase 3 — React Frontend (3 Screens)
**Goal**: A complete, demo-ready UI.  
**Parallel work**: Starts during Phase 2. Person B owns this entirely.

### Global State (Zustand — `store/useAppStore.ts`)
```ts
{
  documents: { id: string, name: string, status: 'indexing'|'ready'|'failed' }[]
  activeDocId: string | null
  chatHistory: { role: 'user'|'assistant', content: string, risk?: string, sources?: [] }[]
  graphData: { nodes: [], edges: [] }
}
```

### Screen 1 — Upload (`/upload`)
- Drag-and-drop zone + file picker (PDF only)
- On upload: POST to `/ingest`, add doc to store with status `indexing`
- Poll `GET /ingest/status/{doc_id}` every 3s, update status badge
- Show list of all indexed documents with status pills: 🟡 Indexing / 🟢 Ready / 🔴 Failed
- Pre-indexed documents are hardcoded in the store initial state as already `ready`
- "Ask questions about this document" button → navigates to `/chat`

### Screen 2 — Chat (`/chat`)
- Standard chat UI, full height
- Each assistant message renders:
  - Answer text
  - Risk badge: `HIGH` (red), `MEDIUM` (amber), `LOW` (green), `UNKNOWN` (grey)
  - Collapsible "Source Clauses" section showing excerpt + filename
  - "View in Graph" button → navigates to `/graph` with relevant nodes highlighted
- Conversation history passed to LightRAG via `QueryParam(conversation_history=[...])`
- Loading state: animated "Analyzing document..." skeleton while waiting

### Screen 3 — Graph (`/graph`)
- Use `react-force-graph-2d` (NOT 3d — 2d is more stable and easier to demo)
  - Install: `npm install react-force-graph-2d`
- On load: fetch `GET /graph`, render all nodes/edges
- If navigated from Chat with node list: fetch `GET /graph/subgraph?nodes=...`, highlight those nodes in a different color (gold), dim others
- Node click: show tooltip with entity name and description
- Controls: zoom in/out, reset view, toggle labels
- Stats bar at top: "147 entities · 203 relationships · 8 documents indexed"

### Navigation
Simple top nav with three links: Upload → Chat → Graph. No router guards, no auth.

### Exit Criteria
- All three screens render without console errors
- Full flow works: upload PDF → see indexing → ask question → see answer with risk badge → click "View in Graph" → see highlighted subgraph
- Works on Chrome on the demo laptop specifically

---

## Phase 4 — Pre-indexing & Data Preparation
**Goal**: 8–10 Indian ToS documents indexed and ready before demo day. Not a code phase — an ops phase.  
**Owner**: Any one person, runs in background while others polish UI.

### Documents to Index (Priority Order)
1. Truecaller ToS — highest impact clause (contact sharing)
2. PhonePe Terms — financial data clauses
3. Paytm Terms — arbitration + data sharing
4. Zomato Terms — location tracking
5. Swiggy Terms — location + payment
6. CRED Terms — credit data access
7. Instagram ToS (Meta) — content ownership
8. Google ToS — data across services
9. Ola/Rapido — GPS + background location
10. IRCTC Terms — government data handling

### Process
```
1. Download PDF (or print-to-PDF from browser)
2. Place in backend/documents/
3. Run: python backend/index_documents.py
   (a simple script that loops over backend/documents/ and calls index_document() for each)
4. Verify in Neo4j browser that nodes appeared
5. Run 3 test queries per document, record expected answers
```

### Build `backend/index_documents.py`
- Loops over all PDFs in `backend/documents/`
- Skips already-indexed files (check `indexing_status` or a simple `indexed.json` manifest)
- Logs progress to terminal

### Exit Criteria
- At least 8 documents indexed with status `ready`
- Each document produces 50+ nodes in Neo4j (if fewer, the PDF extraction failed — recheck)
- Test queries return sensible answers with correct source file attribution

---

## Phase 5 — Integration & Demo Hardening
**Goal**: Everything works together, the demo script runs flawlessly, nothing surprises you on stage.  
**Owner**: All three together.

### Tasks
- [ ] Run the full demo script end-to-end 3 times without touching the keyboard mid-way
- [ ] Add a `.env.demo` with Gemini as primary (more stable than Groq for live demos)
- [ ] Add a simple loading timeout: if `/query` takes >30s, return a graceful error message in the UI
- [ ] Confirm Neo4j Desktop is set to auto-start its database on launch
- [ ] Pre-open three browser tabs before demo: Upload screen, Chat screen, Neo4j browser
- [ ] Disable laptop sleep/screensaver
- [ ] Write a `demo_queries.md` cheatsheet — 5 pre-tested questions with known good answers:
  ```
  1. "Does Truecaller share my phone contacts with advertisers?"
  2. "What does PhonePe do with my transaction history?"
  3. "Can Zomato track my location when the app is closed?"
  4. "What happens if I dispute a charge on CRED?"
  5. "Does Instagram own the photos I upload?"
  ```
- [ ] Prepare a 30-second fallback plan: if internet dies, have Ollama + a local model as last resort

### Exit Criteria
- Demo script runs 3/3 times without failure
- All five cheatsheet questions return HIGH or MEDIUM risk answers with source citations
- Neo4j subgraph highlight works for at least 3 of the 5 queries

---

## Dependency Map

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 5
                    └──► Phase 3 ──► Phase 5
                    └──► Phase 4 ──► Phase 5
```

Phases 2, 3, and 4 can all run in parallel once Phase 1 is done.

---

## What Is Explicitly Out of Scope
- User authentication / sessions
- CUAD dataset
- Reranker model (adds complexity, marginal gain for demo)
- Streaming responses (polling is fine for a demo)
- Cloud deployment
- Database persistence across restarts (Neo4j persists by default — no extra work needed)
- Any document format other than PDF