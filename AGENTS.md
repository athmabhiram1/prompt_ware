# AGENTS.md — Rules for AI Coding Agents

Read CONTEXT.md first. Always. Before writing a single line of code.

---

## Absolute Rules

### Never Break These
- **Do not suggest alternative libraries or frameworks.** The stack is locked. If you think something is a better choice, say so in a comment, then implement what is specified.
- **Do not change the API response shapes.** The `/query` response shape is a contract between backend and frontend. Altering field names or types will silently break the UI.
- **Do not change the embedding model.** `gemini-embedding-2-preview` at 3072 dimensions (default). If vector data already exists, changing this corrupts the entire index. To switch to `EMBED_PROVIDER=ollama` (768-dim), delete `rag_storage/` first.
- **Do not add auth, sessions, or middleware** unless explicitly asked.
- **Do not create new files** without being asked. Add code to existing files first.
- **Do not use `localStorage` or `sessionStorage`** in any frontend artifact.

### Code Style
- Python: async functions wherever LightRAG or Neo4j is involved. Use `await`. No sync wrappers around async code.
- TypeScript: strict types. No `any`. If you don't know the type, ask.
- All secrets come from `.env` via `python-dotenv` on the backend and `import.meta.env` on the frontend. No hardcoded keys, ever.
- Every function that calls an external API must have a `try/except` (Python) or `try/catch` (TS) with a meaningful error message.

### LightRAG-Specific Rules
- Always call `await rag.initialize_storages()` after creating a LightRAG instance.
- Always call `await rag.finalize_storages()` in a `finally` block.
- Always pass `file_paths=[...]` to every `rag.insert()` call. Without this, citations break.
- Use `mode="mix"` for all queries unless explicitly told otherwise.
- Do not use reasoning/thinking models during indexing. Save the best model for query stage.

### LLM Provider Rules
- All LLM and embedding logic lives in `llm_provider.py` only. No other file imports from Groq, Gemini, or Ollama SDKs directly.
- Provider fallback order: Gemini → Groq → Ollama. This order is not negotiable.
- The provider is selected via the `PRIMARY_LLM_PROVIDER` env variable.

---

## What You Should Always Do
- Read the existing file before editing it. Do not rewrite what is already working.
- When adding a new endpoint, add it to the existing FastAPI router — do not create a new `main.py`.
- When in doubt about a requirement, state your assumption explicitly before proceeding.
- Keep functions small. If a function exceeds 40 lines, split it.
- After writing backend code, write the corresponding curl command to test it.

---

## Project Phase Awareness
The project is built in 5 phases. Know which phase you are in:
- **Phase 0**: Environment setup only. No logic.
- **Phase 1**: LightRAG core works as a Python script. No HTTP server yet.
- **Phase 2**: FastAPI endpoints. No frontend yet.
- **Phase 3**: React frontend. Backend must be running for it to work.
- **Phase 4**: Pre-indexing documents. Ops, not code.
- **Phase 5**: Integration and demo hardening. No new features.

Do not build Phase 3 features during Phase 1. Do not add Phase 5 polish during Phase 2.