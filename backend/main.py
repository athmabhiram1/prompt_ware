import asyncio
import logging
import json
import os
import re
import sys
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.limits import RATE_30_PER_MIN, limiter
from app.core.redact import redact_pii
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.upload_guard import (
    MAX_PDF_BYTES,
    check_content_length_header,
    validate_upload,
)

import graph_service
import lightrag_engine
from llm_provider import get_active_rag_storage_dir, get_embedding_func, GEMINI_MODEL_NAME
from request_queue import enqueue, start_worker, stop_all_workers, TaskPriority


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models — response shapes are a frontend contract, do not alter.
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    company_id: str = Field(min_length=1, max_length=128)
    doc_filter: str | None = Field(default=None, max_length=2000)


class SourceClause(BaseModel):
    file: str
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    risk_level: str
    source_clauses: list[SourceClause]
    graph_nodes_involved: list[str]


class IngestResponse(BaseModel):
    status: str
    doc_id: str
    message: str


class StatusResponse(BaseModel):
    doc_id: str
    status: str


class DocumentListItem(BaseModel):
    id: str          # LightRAG internal doc key, e.g. "doc-abc123"
    name: str        # filename, e.g. "telegram_tos.pdf"
    status: str      # ready | indexing | failed
    company_id: str  # which company this belongs to


class DeleteDocumentResponse(BaseModel):
    deleted: bool
    doc_id: str
    company_id: str


class GraphNode(BaseModel):
    id: str
    label: str
    type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str


class GraphStats(BaseModel):
    node_count: int
    edge_count: int


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: GraphStats


class GraphNodeDetail(BaseModel):
    id: str
    label: str
    description: str
    type: str
    source_files: list[str]


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="NyayaMitra — Legal Document Auditor")

# F2: shared slowapi limiter (30/min/IP on guarded endpoints). Wired
# defensively so boot never breaks when slowapi is absent.
app.state.limiter = limiter
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIASGIMiddleware

    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    _HAVE_SLOWAPI_MW = True
except Exception:
    SlowAPIASGIMiddleware = None  # type: ignore[assignment,misc]
    _HAVE_SLOWAPI_MW = False

# ---------------------------------------------------------------------------
# W1.3 env switch + health endpoints (additive; legacy routes below untouched).
# sys.path insert keeps `from app...` working whether uvicorn runs with
# cwd=backend or --app-dir backend (Dockerfile WORKDIR /app + COPY . .).
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from app.core.config import get_settings as _get_w13_settings
    from app.routers.health import router as _health_router

    _w13_settings = _get_w13_settings()
    _w13_settings.validate()  # RuntimeError in prod without API_URL=https://...
    app.include_router(_health_router)
    logger.info(
        "W1.3 config loaded env=%s provider=%s llm_live=%s cache=%s",
        _w13_settings.app_env,
        _w13_settings.llm_provider,
        _w13_settings.llm_live,
        _w13_settings.cache_mode,
    )
except RuntimeError:
    raise
except Exception as exc:  # noqa: BLE001 — additive wiring must never break legacy boot
    logger.warning("W1.3 config/health wiring skipped (non-fatal): %s", exc)
    _w13_settings = None

# W3.1 wiring — deferred W2 routers + brief/options/export (additive, non-fatal).
# Patterns from w2.1-simplify / w2.2-compare / w2.3-qa notepads; one revert-unit
# with brief. Each include is individually guarded so a missing optional dep
# never kills boot; /health /ingest /query /graph stay untouched.
try:
    from app.routers.simplify import router as _simplify_router

    app.include_router(_simplify_router)
    logger.info("W3.1 simplify wired: POST /simplify")
except Exception as exc:  # noqa: BLE001 — additive wiring must never break boot
    logger.warning("W3.1 simplify wiring skipped (non-fatal): %s", exc)
try:
    from app.routers.compare import router as _compare_router

    app.include_router(_compare_router)
    logger.info("W3.1 compare wired: POST /compare")
except Exception as exc:  # noqa: BLE001
    logger.warning("W3.1 compare wiring skipped (non-fatal): %s", exc)
try:
    from app.routers.qa import router as _qa_router

    app.include_router(_qa_router)
    logger.info("W3.1 qa wired: POST /qa")
except Exception as exc:  # noqa: BLE001
    logger.warning("W3.1 qa wiring skipped (non-fatal): %s", exc)
try:
    from app.routers.brief import router as _brief_router

    app.include_router(_brief_router)
    logger.info("W3.1 brief wired: POST /brief")
except Exception as exc:  # noqa: BLE001
    logger.warning("W3.1 brief wiring skipped (non-fatal): %s", exc)
try:
    from app.routers.options import router as _options_router

    app.include_router(_options_router)
    logger.info("W3.1 options wired: POST /options")
except Exception as exc:  # noqa: BLE001
    logger.warning("W3.1 options wiring skipped (non-fatal): %s", exc)
try:
    from app.routers.export import router as _export_router

    app.include_router(_export_router)
    logger.info("W3.1 export wired: GET /export.ics")
except Exception as exc:  # noqa: BLE001
    logger.warning("W3.1 export wiring skipped (non-fatal): %s", exc)
try:
    from app.routers.demo import router as _demo_router

    app.include_router(_demo_router)
    logger.info("W4.1 demo wired: GET /demo/{priya,msme,dpdp}")
except Exception as exc:  # noqa: BLE001
    logger.warning("W4.1 demo wiring skipped (non-fatal): %s", exc)

_indexing_worker_task: asyncio.Task | None = None


@app.on_event("startup")
async def _startup_queue_worker() -> None:
    global _indexing_worker_task
    try:
        _indexing_worker_task = await start_worker("indexing", _indexing_worker_handler, poll_interval=1.0)
        logger.info("Redis indexing worker started")
    except Exception as exc:
        logger.warning("Failed to start Redis indexing worker (non-fatal): %s", exc)


@app.on_event("shutdown")
async def _shutdown_queue_worker() -> None:
    global _indexing_worker_task
    if _indexing_worker_task is not None:
        _indexing_worker_task.cancel()
        try:
            await _indexing_worker_task
        except asyncio.CancelledError:
            pass
    await stop_all_workers()

_cors_origins = ["http://localhost:5173", "http://localhost:3000"]
_frontend_url = (_w13_settings.frontend_url if _w13_settings else "").strip()
if _frontend_url and _frontend_url not in _cors_origins:
    _cors_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
if _HAVE_SLOWAPI_MW:
    app.add_middleware(SlowAPIASGIMiddleware)

# In-memory status for in-flight indexing jobs: key = "<company_id>/<doc_filename>"
indexing_status: dict[str, str] = {}
indexing_locks: dict[str, asyncio.Lock] = {}


def _get_indexing_lock(status_key: str) -> asyncio.Lock:
    if status_key not in indexing_locks:
        indexing_locks[status_key] = asyncio.Lock()
    return indexing_locks[status_key]



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_company_id(raw: str) -> str:
    """Sanitise company_id to a filesystem-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", raw.strip()).strip("_")
    if not slug:
        raise HTTPException(status_code=400, detail="company_id must not be empty")
    return slug.lower()


def _normalize_doc_status(raw: str | None) -> str:
    normalized = (raw or "").strip().lower()
    if normalized in {"processed", "ready", "completed"}:
        return "ready"
    if normalized in {"processing", "indexing", "running"}:
        return "indexing"
    if normalized in {"failed", "error"}:
        return "failed"
    return "indexing"


def _safe_load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_documents_for_company(company_id: str) -> list[DocumentListItem]:
    """Load all indexed documents for a single company.

    PG-aware: when Postgres is configured, doc rows live in PG tables
    (PGDocStatusStorage), not Mongo collections or local kv_store JSON — the
    live PG listing query is T6 key-gated work, so this serves the in-flight
    overlay only. Otherwise reads from MongoDB when MONGO_URI is set,
    else local JSON files.
    """
    mongo_uri = os.getenv("MONGO_URI", "").strip()
    if lightrag_engine._postgres_configured():
        docs: list[DocumentListItem] = []
    elif mongo_uri:
        from pymongo import MongoClient
        database_name = os.getenv("MONGO_DATABASE", "nyayamitra").strip()
        client = MongoClient(mongo_uri)
        db = client[database_name]
        if company_id == "default_company":
            full_docs_coll = db["full_docs"]
            doc_status_coll = db["doc_status"]
        else:
            full_docs_coll = db[f"{company_id}_full_docs"]
            doc_status_coll = db[f"{company_id}_doc_status"]
        docs: list[DocumentListItem] = []
        for doc in full_docs_coll.find():
            doc_key = doc.get("_id", "")
            file_path = str(doc.get("file_path", "")).strip()
            if not file_path:
                continue
            doc_name = Path(file_path).name
            status_doc = doc_status_coll.find_one({"_id": doc_key})
            status = _normalize_doc_status(
                status_doc.get("status") if status_doc else None
            )
            docs.append(DocumentListItem(id=doc_key, name=doc_name, status=status, company_id=company_id))
        client.close()
    else:
        if company_id == "default_company":
            company_dir = get_active_rag_storage_dir()
        else:
            company_dir = get_active_rag_storage_dir() / company_id
        full_docs = _safe_load_json(company_dir / "kv_store_full_docs.json")
        doc_status = _safe_load_json(company_dir / "kv_store_doc_status.json")
        docs: list[DocumentListItem] = []
        for doc_key, doc_data in full_docs.items():
            if not isinstance(doc_data, dict):
                continue
            file_path = str(doc_data.get("file_path", "")).strip()
            if not file_path:
                continue
            doc_name = Path(file_path).name
            status_data = doc_status.get(doc_key, {}) if isinstance(doc_status, dict) else {}
            status = _normalize_doc_status(
                status_data.get("status") if isinstance(status_data, dict) else None
            )
            docs.append(DocumentListItem(id=doc_key, name=doc_name, status=status, company_id=company_id))

    # Overlay in-flight status for this company
    for key, status in indexing_status.items():
        comp_id, doc_name = key.split("/", 1) if "/" in key else ("unknown", key)
        if comp_id != company_id:
            continue
        for doc in docs:
            if doc.name == doc_name:
                doc.status = _normalize_doc_status(status)
                break
        else:
            docs.append(DocumentListItem(
                id=doc_name,
                name=doc_name,
                status=_normalize_doc_status(status),
                company_id=company_id,
            ))

    return docs


def _load_all_documents() -> list[DocumentListItem]:
    """Load documents across all companies from PG, Mongo or local JSON."""
    mongo_uri = os.getenv("MONGO_URI", "").strip()
    if lightrag_engine._postgres_configured():
        # PG-aware: workspace enumeration over PG tables is T6 live work;
        # seed from in-flight keys below via the overlay.
        companies: set[str] = set()
    elif mongo_uri:
        from pymongo import MongoClient
        database_name = os.getenv("MONGO_DATABASE", "nyayamitra").strip()
        client = MongoClient(mongo_uri)
        db = client[database_name]
        companies = set()
        for coll_name in db.list_collection_names():
            if coll_name.endswith("_full_docs"):
                companies.add(coll_name[: -len("_full_docs")])
        if "full_docs" in db.list_collection_names():
            companies.add("default_company")
        client.close()
    else:
        docs_dir = Path(__file__).resolve().parent / "documents"
        companies = set()
        if docs_dir.exists():
            companies.update({d.name for d in docs_dir.iterdir() if d.is_dir()})
        base = get_active_rag_storage_dir()
        if base.exists() and (base / "kv_store_full_docs.json").exists():
            companies.add("default_company")

    all_docs: list[DocumentListItem] = []
    for company_id in sorted(companies):
        all_docs.extend(_load_documents_for_company(company_id))

    # Overlay in-flight status
    for key, status in indexing_status.items():
        company_id, doc_name = key.split("/", 1) if "/" in key else ("unknown", key)
        # Find and update existing entry or add a placeholder
        for doc in all_docs:
            if doc.company_id == company_id and doc.name == doc_name:
                doc.status = _normalize_doc_status(status)
                break
        else:
            all_docs.append(DocumentListItem(
                id=doc_name,
                name=doc_name,
                status=_normalize_doc_status(status),
                company_id=company_id,
            ))

    return all_docs


async def _unload_ollama_models() -> None:
    primary_provider = os.getenv("PRIMARY_LLM_PROVIDER", "gemini").strip().lower()
    if primary_provider == "ollama":
        ollama_base = os.getenv("OLLAMA_BASE_URL", "").strip()
        if not ollama_base:
            logger.info("Ollama unload skipped (OLLAMA_BASE_URL unset; dev-only opt-in)")
            return
        from llm_provider import _resolve_ollama_url
        ollama_base = _resolve_ollama_url(ollama_base)
        llm_model = os.getenv("OLLAMA_LLM_MODEL", "qwen3.5:9b").strip()
        embed_model = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b").strip()
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info("Auto-unloading Ollama LLM model: %s", llm_model)
                await client.post(f"{ollama_base}/api/chat", json={"model": llm_model, "keep_alive": 0})
                logger.info("Auto-unloading Ollama embedding model: %s", embed_model)
                await client.post(f"{ollama_base}/api/chat", json={"model": embed_model, "keep_alive": 0})
        except Exception as unload_exc:
            logger.warning("Failed to auto-unload Ollama models: %s", unload_exc)


async def _run_indexing(company_id: str, doc_id: str, saved_path: str) -> None:
    status_key = f"{company_id}/{doc_id}"
    lock = _get_indexing_lock(status_key)

    if lock.locked():
        logger.warning("Indexing task already running for %s, skipping duplicate execution.", redact_pii(status_key))
        return

    async with lock:
        try:
            # Double check status before starting expensive operation
            if indexing_status.get(status_key) == "ready":
                logger.info("Document %s already indexed, skipping duplicate.", redact_pii(status_key))
                return
            await lightrag_engine.index_document(saved_path, company_id)
            indexing_status[status_key] = "ready"
        except Exception as exc:
            indexing_status[status_key] = "failed"
            logger.exception(
                "Indexing failed company=%s doc=%s: %s",
                redact_pii(company_id),
                redact_pii(doc_id),
                redact_pii(exc),
            )
        finally:
            await _unload_ollama_models()


async def _indexing_worker_handler(task_data: dict) -> None:
    payload = task_data.get("payload", {})
    company_id = payload.get("company_id", "")
    doc_id = payload.get("doc_id", "")
    saved_path = payload.get("saved_path", "")
    if company_id and doc_id and saved_path:
        await _run_indexing(company_id, doc_id, saved_path)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/ingest", response_model=IngestResponse)
@limiter.limit(RATE_30_PER_MIN)
async def ingest(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    company_id: str = Form(...),
) -> IngestResponse:
    """Upload a PDF and index it under the given company workspace.

    The company_id isolates this document from all other companies.
    Re-uploading the same file to the same company is a safe no-op (deduped by LightRAG).
    Re-uploading to a different company creates an independent copy in that workspace.
    """
    check_content_length_header(request.headers.get("content-length"))
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename")

    safe_company = _safe_company_id(company_id)

    documents_dir = Path(__file__).resolve().parent / "documents" / safe_company
    documents_dir.mkdir(parents=True, exist_ok=True)

    doc_id = Path(file.filename).name
    saved_path = str(documents_dir / doc_id)
    status_key = f"{safe_company}/{doc_id}"

    # Check lock and indexing status to prevent duplicate indexing
    current_status = indexing_status.get(status_key)
    if current_status == "indexing":
        return IngestResponse(
            status="indexing",
            doc_id=doc_id,
            message=f"Document '{doc_id}' is already being indexed."
        )
    elif current_status == "ready":
        return IngestResponse(
            status="ready",
            doc_id=doc_id,
            message=f"Document '{doc_id}' is already indexed."
        )

    # Check database status as well
    existing_docs = _load_documents_for_company(safe_company)
    for doc in existing_docs:
        if doc.name == doc_id:
            if doc.status == "indexing":
                indexing_status[status_key] = "indexing"
                return IngestResponse(
                    status="indexing",
                    doc_id=doc_id,
                    message=f"Document '{doc_id}' is already being indexed."
                )
            elif doc.status == "ready":
                indexing_status[status_key] = "ready"
                return IngestResponse(
                    status="ready",
                    doc_id=doc_id,
                    message=f"Document '{doc_id}' is already indexed."
                )

    try:
        content = await file.read(MAX_PDF_BYTES + 1)
        validate_upload(file.filename, file.content_type, content)
        with open(saved_path, "wb") as out_file:
            out_file.write(content)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to store uploaded file") from None
    finally:
        await file.close()

    indexing_status[status_key] = "indexing"

    try:
        await enqueue(
            "indexing",
            {"company_id": safe_company, "doc_id": doc_id, "saved_path": saved_path},
            priority=TaskPriority.NORMAL,
            max_retries=2,
        )
        logger.info("Indexing task enqueued company=%s doc=%s", safe_company, redact_pii(doc_id))
    except Exception as exc:
        logger.warning("Redis queue unavailable, falling back to BackgroundTask: %s", exc)
        background_tasks.add_task(_run_indexing, safe_company, doc_id, saved_path)

    return IngestResponse(status="indexing", doc_id=doc_id, message=f"Indexing started for company '{safe_company}'")


@app.get("/ingest/status/{company_id}/{doc_id}", response_model=StatusResponse)
async def ingest_status(company_id: str, doc_id: str) -> StatusResponse:
    safe_company = _safe_company_id(company_id)
    status_key = f"{safe_company}/{doc_id}"

    if status_key in indexing_status:
        return StatusResponse(doc_id=doc_id, status=_normalize_doc_status(indexing_status[status_key]))

    for doc in _load_documents_for_company(safe_company):
        if doc.name == doc_id:
            return StatusResponse(doc_id=doc_id, status=doc.status)

    raise HTTPException(status_code=404, detail="Unknown doc_id for this company")


@app.get("/documents", response_model=list[DocumentListItem])
async def list_documents_endpoint(company_id: str | None = None) -> list[DocumentListItem]:
    """List all indexed documents. Pass ?company_id=<id> to filter by company."""
    if company_id:
        return _load_documents_for_company(_safe_company_id(company_id))
    return _load_all_documents()


@app.get("/workspaces", response_model=list[str])
async def get_workspaces_endpoint() -> list[str]:
    """List all active company/workspace IDs."""
    mongo_uri = os.getenv("MONGO_URI", "").strip()
    if lightrag_engine._postgres_configured():
        # PG-aware: workspace enumeration over PG tables is T6 live work;
        # derive from in-flight indexing keys only.
        companies = {key.split("/", 1)[0] for key in indexing_status if "/" in key}
    elif mongo_uri:
        from pymongo import MongoClient
        database_name = os.getenv("MONGO_DATABASE", "nyayamitra").strip()
        client = MongoClient(mongo_uri)
        db = client[database_name]
        companies = set()
        for coll_name in db.list_collection_names():
            if coll_name.endswith("_full_docs"):
                companies.add(coll_name[: -len("_full_docs")])
        client.close()
    else:
        docs_dir = Path(__file__).resolve().parent / "documents"
        companies = set()
        if docs_dir.exists():
            companies.update({f.name for f in docs_dir.iterdir() if f.is_dir()})

    if "default_company" not in companies:
        companies.add("default_company")
    return sorted(companies)


async def _resolve_doc_id(doc_id: str, company_id: str) -> str:
    """Resolve a document ID that may be a filename to the internal UUID key.

    The ingest endpoint stores docs with filename as the key in indexing_status,
    while LightRAG's internal storage uses UUID keys (doc-abc123...).
    This helper resolves filename -> UUID so callers can use either format.
    """
    if doc_id.startswith("doc-"):
        return doc_id
    for doc in _load_documents_for_company(company_id):
        if doc.name == doc_id or doc.id == doc_id:
            return doc.id
    return doc_id


@app.delete("/documents/{company_id}/{doc_id}", response_model=DeleteDocumentResponse)
async def delete_document_endpoint(company_id: str, doc_id: str) -> DeleteDocumentResponse:
    """Remove a document from a company's workspace.

    doc_id can be the LightRAG internal UUID key (doc-abc123...) or the filename.
    This removes the document's chunks, graph nodes, and vector embeddings.
    Other documents in the same company are unaffected.
    """
    safe_company = _safe_company_id(company_id)
    resolved = await _resolve_doc_id(doc_id, safe_company)
    if not resolved.startswith("doc-"):
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found in company '{safe_company}'")
    deleted = await lightrag_engine.delete_document(resolved, safe_company)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found in company '{safe_company}'")
    # Clean up in-memory status for both UUID and filename keys
    indexing_status.pop(f"{safe_company}/{resolved}", None)
    indexing_status.pop(f"{safe_company}/{doc_id}", None)
    return DeleteDocumentResponse(deleted=True, doc_id=resolved, company_id=safe_company)


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(body: QueryRequest) -> QueryResponse:
    safe_company = _safe_company_id(body.company_id)
    try:
        result = await lightrag_engine.query(body.question, safe_company, doc_filter=body.doc_filter)
        source_clauses = [SourceClause(**clause) for clause in result.get("source_clauses", [])]
        return QueryResponse(
            answer=str(result.get("answer", "")),
            risk_level=str(result.get("risk_level", "UNKNOWN")),
            source_clauses=source_clauses,
            graph_nodes_involved=[str(n) for n in result.get("graph_nodes_involved", [])],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc
    finally:
        await _unload_ollama_models()


@app.get("/graph", response_model=GraphResponse)
async def graph_endpoint(company_id: str, doc_filter: str | None = None) -> GraphResponse:
    safe_company = _safe_company_id(company_id)
    graph = await graph_service.get_full_graph_for_doc(doc_filter, company_id=safe_company)
    return GraphResponse(**graph)


@app.get("/graph/subgraph", response_model=GraphResponse)
async def graph_subgraph_endpoint(
    nodes: str,
    company_id: str,
    doc_filter: str | None = None,
) -> GraphResponse:
    safe_company = _safe_company_id(company_id)
    node_ids = [n.strip() for n in nodes.split(",") if n.strip()]
    graph = await graph_service.get_subgraph_for_doc(node_ids, doc_filter=doc_filter, company_id=safe_company)
    return GraphResponse(**graph)


@app.get("/graph/node/{node_id}", response_model=GraphNodeDetail)
async def graph_node_detail_endpoint(node_id: str) -> GraphNodeDetail:
    try:
        detail = await graph_service.get_node_details(node_id)
        return GraphNodeDetail(**detail)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch node details: {exc}") from exc


class ProviderSettings(BaseModel):
    mode: str
    primary_llm_provider: str
    embed_provider: str
    query_model: str
    embedding_model: str
    embedding_dim: int
    requires_reindex: bool
    warning: str | None = None


class UpdateSettingsRequest(BaseModel):
    use_local_ollama: bool
    query_model: str
    embedding_model: str
    embedding_dim: int


@app.get("/settings/provider", response_model=ProviderSettings)
async def get_settings_provider() -> ProviderSettings:
    primary = os.getenv("PRIMARY_LLM_PROVIDER", "gemini").lower()
    embed = os.getenv("EMBED_PROVIDER", "gemini").lower()
    mode = "local_ollama" if (primary == "ollama" or embed == "ollama") else "cloud"
    
    # Resolve parameters from the active embedding function
    embed_func = get_embedding_func()
    resolved_dim = getattr(embed_func, "embedding_dim", 3072)
    resolved_model = getattr(embed_func, "model_name", "gemini-embedding-2-preview")
    
    return ProviderSettings(
        mode=mode,
        primary_llm_provider=primary,
        embed_provider=embed,
        query_model=os.getenv("OLLAMA_LLM_MODEL", "qwen3:8b") if primary == "ollama" else GEMINI_MODEL_NAME,
        embedding_model=resolved_model,
        embedding_dim=resolved_dim,
        requires_reindex=False,
        warning=None
    )


@app.post("/settings/provider", response_model=ProviderSettings)
async def set_settings_provider(body: UpdateSettingsRequest) -> ProviderSettings:
    if body.use_local_ollama:
        os.environ["PRIMARY_LLM_PROVIDER"] = "ollama"
        os.environ["EMBED_PROVIDER"] = "ollama"
    else:
        # Revert to standard cloud config
        os.environ["PRIMARY_LLM_PROVIDER"] = "gemini"
        os.environ["EMBED_PROVIDER"] = "gemini"
    
    return await get_settings_provider()
