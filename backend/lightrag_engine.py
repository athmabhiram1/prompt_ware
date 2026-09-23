import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from dotenv import load_dotenv
from lightrag import LightRAG, QueryParam
from lightrag.kg.neo4j_impl import Neo4JStorage as _Neo4JStorage

from document_loader import load_pdf
from graph_service import get_subgraph_for_doc
from llm_provider import get_active_rag_storage_dir, get_embedding_func, get_llm_func
from request_queue import enqueue, TaskPriority

from app.core.redact import redact_pii


load_dotenv(override=True)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Monkey-patch: semantic relationship types in Neo4j
#
# LightRAG hardcodes MERGE (source)-[r:DIRECTED]-(target) for every edge.
# The actual semantic relationship is in edge_data["keywords"] (e.g.
# "data sharing,privacy,consent"). This patch replaces the fixed DIRECTED
# type with the first keyword, normalised to UPPER_SNAKE_CASE, so the Neo4j
# graph shows meaningful edge labels (DATA_SHARING, GOVERNANCE, etc.).
#
# Relationship types in Cypher cannot be parameterised, so the type must be
# baked into the query string — hence the need for a patch rather than a
# query parameter.
# ---------------------------------------------------------------------------

def _keywords_to_rel_type(keywords: str) -> str:
    """Return a Neo4j-safe relationship type derived from the first keyword."""
    if not keywords:
        return "RELATED_TO"
    first_kw = keywords.split(",")[0].strip()
    sanitized = re.sub(r"[^a-zA-Z0-9 ]", "", first_kw)
    return sanitized.strip().upper().replace(" ", "_") or "RELATED_TO"


async def _semantic_upsert_edge(
    self: _Neo4JStorage,
    source_node_id: str,
    target_node_id: str,
    edge_data: dict,
) -> None:
    from lightrag.utils import logger

    rel_type = _keywords_to_rel_type(edge_data.get("keywords", ""))
    try:
        async with self._driver.session(database=self._DATABASE) as session:
            async def execute_upsert(tx):
                workspace_label = self._get_workspace_label()
                query = f"""
                MATCH (source:`{workspace_label}` {{entity_id: $source_entity_id}})
                WITH source
                MATCH (target:`{workspace_label}` {{entity_id: $target_entity_id}})
                MERGE (source)-[r:{rel_type}]-(target)
                SET r += $properties
                RETURN r, source, target
                """
                result = await tx.run(
                    query,
                    source_entity_id=source_node_id,
                    target_entity_id=target_node_id,
                    properties=edge_data,
                )
                try:
                    await result.fetch(2)
                finally:
                    await result.consume()

            await session.execute_write(execute_upsert)
    except Exception as exc:
        logger.error(f"[{self.workspace}] Semantic edge upsert failed: {exc}")
        raise


_Neo4JStorage.upsert_edge = _semantic_upsert_edge  # type: ignore[method-assign]

# Appended to every query so the LLM returns structured metadata in a
# parseable block. Phase 2 reads risk_level, source_clauses, and
# graph_nodes_involved directly from the dict this function returns.
_ANALYSIS_PROMPT = """
You are NyayaMitra's legal explainer assistant.
Write for non-lawyers using concise plain language.
Before writing, infer the best visual markdown structure for the specific question and use ONE:
1) checklist (for obligations/limits/requirements),
2) comparison table (for alternatives/tiers),
3) timeline steps (for process/questions about sequence),
4) risk matrix bullets (for legal or financial risk).

Always include these sections in markdown:
### Direct answer
### Key points
### What to do next

Formatting rules:
- Do NOT output any internal thinking, reasoning process, chain-of-thought, or <think> tags. Output your final response directly.
- Use short bullets, not long paragraphs.
- Keep total length under 220 words unless user explicitly asks for detail.
- Bold critical terms (deadlines, limits, penalties, rights).
- If uncertain, include a short "Unknowns" bullet.
- Do not invent clauses. Use only retrieved context.

After your answer, append this exact block — nothing after it:

[ANALYSIS]
{"risk_level": "HIGH|MEDIUM|LOW", "graph_nodes_involved": ["entity1", "entity2"], "source_clauses": [{"file": "filename.pdf", "excerpt": "exact quoted text from the document"}]}
[/ANALYSIS]

Rules:
- Do NOT include any thoughts or reasoning in the JSON block or surrounding text.
- risk_level: HIGH = serious data/financial/legal risk; MEDIUM = moderate concern; LOW = routine clause.
- graph_nodes_involved: 2-5 key entity names from the document relevant to this answer.
- source_clauses: 1-3 direct verbatim quotes from the source document supporting your answer.
- Output valid JSON only inside the [ANALYSIS] block."""


def _resolve_neo4j_env() -> None:
    """Point NEO4J_* env vars at the first configured target that is reachable.

    LightRAG's Neo4JStorage reads NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD /
    NEO4J_DATABASE directly from the environment. Target order is controlled
    by neo4j_connection._candidate_targets() and can be overridden with
    NEO4J_TARGET=local|cloud.
    """
    from neo4j_connection import _candidate_targets
    import socket

    for target in _candidate_targets():
        if not target.password:
            continue
        try:
            host = target.uri.split("://")[-1].split(":")[0]
            port = int(target.uri.split(":")[-1]) if ":" in target.uri.split("://")[-1] else 7687
            with socket.create_connection((host, port), timeout=2):
                os.environ["NEO4J_URI"] = target.uri
                os.environ["NEO4J_USERNAME"] = target.username
                os.environ["NEO4J_PASSWORD"] = target.password
                os.environ["NEO4J_DATABASE"] = target.database
                print(f"Routing LightRAG Neo4j to active target: {target.name} ({target.uri})", flush=True)
                return
        except Exception:
            continue
    raise RuntimeError(
        "No Neo4j target is reachable. Ensure Neo4j is running and accessible."
    )


def _neo4j_available() -> bool:
    """Quick check: can we reach any configured Neo4j target?"""
    from neo4j_connection import _candidate_targets
    import socket
    for target in _candidate_targets():
        if not target.password:
            continue
        try:
            host = target.uri.split("://")[-1].split(":")[0]
            port = int(target.uri.split(":")[-1]) if ":" in target.uri.split("://")[-1] else 7687
            with socket.create_connection((host, port), timeout=2):
                return True
        except Exception:
            continue
    return False


def _mongo_configured() -> bool:
    """Quick check: is MONGO_URI set in environment?"""
    return bool(os.getenv("MONGO_URI", "").strip())


_PG_ENV_KEYS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DATABASE",
)


def _bridge_database_url_to_postgres_env() -> None:
    """Derive missing POSTGRES_* vars from DATABASE_URL (Neon pooled URL).

    LightRAG's postgres_impl reads POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE
    (+ POSTGRES_SSL_MODE) directly from the environment and ignores
    DATABASE_URL natively — this bridge is the whole point: a DATABASE_URL-only
    deploy (Render blueprint) still feeds LightRAG what it expects.

    Rules: parse host/port/user/password/db from DATABASE_URL; set each
    POSTGRES_* only when absent (never clobber explicit POSTGRES_*);
    default POSTGRES_SSL_MODE=require when absent (Neon mandates TLS).

    Pooled-URL knob (Neon pgbouncer): pooled connections are transactional, so
    asyncpg must disable the prepared-statement cache — pass
    statement_cache_size=0 (statement-cache-0) in the asyncpg connect kwargs
    wherever the pool is opened, or use the session-pooled (non-transactional)
    endpoint. Documented here because the bridge keeps pooled URLs working.
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return
    try:
        parsed = urlparse(database_url)
        if not parsed.hostname:
            return
    except ValueError:
        return
    bridged = {
        "POSTGRES_HOST": parsed.hostname,
        "POSTGRES_PORT": str(parsed.port or 5432),
        "POSTGRES_USER": unquote(parsed.username or ""),
        "POSTGRES_PASSWORD": unquote(parsed.password or ""),
        "POSTGRES_DATABASE": unquote((parsed.path or "").lstrip("/")),
    }
    for key, value in bridged.items():
        if value and not os.getenv(key, "").strip():
            os.environ[key] = value
    if not os.getenv("POSTGRES_SSL_MODE", "").strip():
        os.environ["POSTGRES_SSL_MODE"] = "require"


def _postgres_configured() -> bool:
    """Quick check: is Postgres configured via POSTGRES_* trio or DATABASE_URL?"""
    _bridge_database_url_to_postgres_env()
    trio = all(os.getenv(k, "").strip() for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DATABASE"))
    return bool(trio or os.getenv("DATABASE_URL", "").strip())


def _build_rag(company_id: str) -> LightRAG:
    """Build a LightRAG instance scoped to a specific company workspace.

    LightRAG creates <working_dir>/<workspace>/ for all storage files.
    We set working_dir to the base embedding dir and workspace=company_id,
    so files land at rag_storage/<embed_ns>/<company_id>/*.json and Neo4j
    nodes carry the company_id label — fully isolated per company.

    Storage priority: Postgres first (PGKVStorage + PGVectorStorage +
    PGDocStatusStorage + PGTableGraphStorage via the pgtable_impl backend,
    which needs no Apache AGE extension and runs on Neon), then Mongo, then
    JSON/NetworkX file defaults. The Neo4j/NetworkX fork below only applies
    to the non-PG path.

    FIDELITY CAVEAT (Neo4j-only, do NOT port — out of scope, flagged for
    later): _semantic_upsert_edge monkey-patches Neo4JStorage.upsert_edge so
    graph edges carry UPPER_SNAKE relationship types derived from keywords.
    PGTableGraphStorage has no equivalent hook here, so PG-backed graphs keep
    LightRAG's default edge labelling until a PG-side upsert is implemented.
    """
    llm_func, llm_model_name = get_llm_func()
    embedding_func = get_embedding_func()
    base_dir = str(get_active_rag_storage_dir())

    if _postgres_configured():
        print(f"[{company_id}] Postgres configured — using PGKVStorage+PGVectorStorage+PGDocStatusStorage+PGTableGraphStorage")
        return LightRAG(
            working_dir=base_dir,
            workspace="" if company_id == "default_company" else company_id,
            llm_model_func=llm_func,
            llm_model_name=llm_model_name,
            embedding_func=embedding_func,
            graph_storage="PGTableGraphStorage",
            kv_storage="PGKVStorage",
            vector_storage="PGVectorStorage",
            doc_status_storage="PGDocStatusStorage",
            entity_extract_max_gleaning=0,
        )

    if _neo4j_available():
        _resolve_neo4j_env()
        graph_storage = "Neo4JStorage"
    else:
        graph_storage = "NetworkXStorage"
        print(f"[{company_id}] Neo4j unavailable — using NetworkXStorage (file-based graph)")

    kv_storage = "JsonKVStorage"
    vector_storage = "NanoVectorDBStorage"
    doc_status_storage = "JsonDocStatusStorage"

    if _mongo_configured():
        kv_storage = "MongoKVStorage"
        vector_storage = "MongoVectorDBStorage"
        doc_status_storage = "MongoDocStatusStorage"
        print(f"[{company_id}] MongoDB configured — using MongoKVStorage+VectorDBStorage+DocStatusStorage")

    return LightRAG(
        working_dir=base_dir,
        workspace="" if company_id == "default_company" else company_id,
        llm_model_func=llm_func,
        llm_model_name=llm_model_name,
        embedding_func=embedding_func,
        graph_storage=graph_storage,
        kv_storage=kv_storage,
        vector_storage=vector_storage,
        doc_status_storage=doc_status_storage,
        entity_extract_max_gleaning=0,
    )


def _parse_analysis_block(raw: str) -> dict[str, object]:
    """Extract and parse the [ANALYSIS] JSON block from the LLM response.

    Returns a dict with risk_level, graph_nodes_involved, source_clauses.
    Falls back to safe defaults if the block is absent or malformed.
    """
    match = re.search(r"\[ANALYSIS\](.*?)\[/ANALYSIS\]", raw, re.DOTALL)
    if not match:
        return {"risk_level": "UNKNOWN", "graph_nodes_involved": [], "source_clauses": []}
    try:
        parsed = json.loads(match.group(1).strip())
        return {
            "risk_level": parsed.get("risk_level", "UNKNOWN"),
            "graph_nodes_involved": parsed.get("graph_nodes_involved", []),
            "source_clauses": parsed.get("source_clauses", []),
        }
    except (json.JSONDecodeError, AttributeError):
        return {"risk_level": "UNKNOWN", "graph_nodes_involved": [], "source_clauses": []}


def _normalize_graph_nodes(nodes: object) -> list[str]:
    if not isinstance(nodes, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        text = str(node).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized[:8]


async def _filter_graph_nodes_against_db(nodes: list[str], doc_filter: str | None, company_id: str) -> list[str]:
    if not nodes:
        return []
    try:
        subgraph = await get_subgraph_for_doc(nodes, doc_filter=doc_filter, company_id=company_id)
        existing = {str(node.get("id", "")).strip() for node in subgraph.get("nodes", []) if isinstance(node, dict)}
        filtered = [node for node in nodes if node in existing]
        return filtered if filtered else nodes
    except Exception:
        return nodes


async def _prewarm_ollama() -> None:
    """Send a minimal request to Ollama to load the model into VRAM before indexing.

    Avoids cold-start latency on the first real chunk. Only runs when
    PRIMARY_LLM_PROVIDER=ollama; silently skips on failure so indexing
    still proceeds.
    """
    from llm_provider import _getenv, _resolve_ollama_url
    if _getenv("PRIMARY_LLM_PROVIDER", "gemini").lower() != "ollama":
        return
    ollama_base_url = _resolve_ollama_url(_getenv("OLLAMA_BASE_URL", ""))
    if not ollama_base_url:
        logger.info("Ollama pre-warm skipped (OLLAMA_BASE_URL unset; dev-only opt-in)")
        return
    model = _getenv("OLLAMA_LLM_MODEL", "qwen3:8b")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await client.post(
                f"{ollama_base_url}/api/generate",
                json={"model": model, "prompt": "hi", "stream": False, "options": {"num_predict": 1}},
            )
        logger.info("Ollama pre-warm complete model=%s", model)
    except Exception as exc:
        logger.warning("Ollama pre-warm failed (non-fatal): %s", exc)


def _validate_entities_against_text(company_id: str, source_text: str) -> int:
    """Remove hallucinated entities from kv_store that don't appear in source text.

    LightRAG's LLM-based entity extraction sometimes generates entities not
    present in the source document. This function filters them out by checking
    each entity name against the original text.

    Storage-aware: when Postgres is configured the entity store lives in PG
    tables (PGKVStorage), not kv_store_full_entities.json, so there is no
    local file to validate — returns 0 and leaves PG rows to the T6 live
    path. The JSON-file filter below applies to the non-PG path only.

    Returns the number of entities removed.
    """
    if _postgres_configured():
        logger.info("Entity validation skipped (entities live in Postgres, not local JSON)")
        return 0
    text_lower = source_text.lower()
    if company_id == "default_company":
        company_dir = get_active_rag_storage_dir()
    else:
        company_dir = get_active_rag_storage_dir() / company_id
    full_entities_path = company_dir / "kv_store_full_entities.json"
    if not full_entities_path.exists():
        return 0

    try:
        with open(full_entities_path, encoding="utf-8") as f:
            entities_data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Entity validation failed to read kv_store: %s", exc)
        return 0

    total_removed = 0
    changed = False
    for doc_key, doc_data in entities_data.items():
        if not isinstance(doc_data, dict):
            continue
        entity_names = doc_data.get("entity_names", [])
        if not isinstance(entity_names, list):
            continue
        filtered = []
        for name in entity_names:
            name_str = str(name).strip()
            if not name_str:
                continue
            if name_str.lower() in text_lower:
                filtered.append(name)
            else:
                total_removed += 1
                logger.debug("Removed hallucinated entity from doc %s", redact_pii(doc_key))
        if len(filtered) != len(entity_names):
            doc_data["entity_names"] = filtered
            changed = True

    if changed:
        try:
            with open(full_entities_path, "w", encoding="utf-8") as f:
                json.dump(entities_data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.warning("Entity validation failed to write kv_store: %s", exc)
            return 0

    return total_removed


async def index_document(pdf_path: str, company_id: str = "default_company") -> None:
    """Index a PDF into the company-scoped LightRAG workspace.

    Safe to call multiple times — LightRAG deduplicates by content hash.
    A second upload of the same file is a no-op (status: duplicate/failed),
    existing documents in the workspace are never removed.
    """
    overall_start = time.perf_counter()
    load_start = time.perf_counter()
    text, metadata = load_pdf(pdf_path)
    load_elapsed = time.perf_counter() - load_start
    logger.info(
        "Indexing start company=%s file=%s pages=%s chars=%d load_elapsed=%.3fs",
        redact_pii(company_id),
        redact_pii(metadata["filename"]),
        metadata["page_count"],
        len(text),
        load_elapsed,
    )

    rag = _build_rag(company_id)
    await _prewarm_ollama()
    init_start = time.perf_counter()
    await rag.initialize_storages()
    init_elapsed = time.perf_counter() - init_start
    logger.info("Indexing storages initialized company=%s elapsed=%.3fs", redact_pii(company_id), init_elapsed)
    try:
        insert_start = time.perf_counter()
        await rag.ainsert(input=[text], file_paths=[pdf_path])
        insert_elapsed = time.perf_counter() - insert_start
        logger.info("Indexing insert completed company=%s elapsed=%.3fs", redact_pii(company_id), insert_elapsed)
    finally:
        finalize_start = time.perf_counter()
        await rag.finalize_storages()
        finalize_elapsed = time.perf_counter() - finalize_start
        overall_elapsed = time.perf_counter() - overall_start
        logger.info(
            "Indexing finalized company=%s finalize_elapsed=%.3fs total_elapsed=%.3fs",
            company_id,
            finalize_elapsed,
            overall_elapsed,
        )

    validate_start = time.perf_counter()
    removed = _validate_entities_against_text(company_id, text)
    validate_elapsed = time.perf_counter() - validate_start
    if removed:
        logger.info(
            "Entity validation removed %d hallucinated entities company=%s elapsed=%.3fs",
            removed, company_id, validate_elapsed,
        )


async def delete_document(doc_id: str, company_id: str) -> bool:
    """Remove a document from the company-scoped LightRAG workspace.

    doc_id is the LightRAG internal doc key (e.g. 'doc-abc123...').
    Returns True if deleted, False if not found.
    """
    rag = _build_rag(company_id)
    await rag.initialize_storages()
    try:
        result = await rag.adelete_by_doc_id(doc_id)
        return result.status == "success"
    except Exception as exc:
        print(f"delete_document failed company={company_id} doc_id={doc_id}: {exc}")
        return False
    finally:
        await rag.finalize_storages()


async def query(question: str, company_id: str = "default_company", doc_filter: str | None = None) -> dict[str, object]:
    """Query the indexed documents for a specific company workspace.

    Returns:
        {
            "answer": str,
            "risk_level": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
            "source_clauses": [{"file": str, "excerpt": str}],
            "graph_nodes_involved": [str],
        }
    """
    rag = _build_rag(company_id)
    await rag.initialize_storages()
    try:
        # QueryParam.ids was removed in lightrag-hku v1.4.11. When doc_filter
        # is set we inject a constraint into user_prompt instead, which the LLM
        # honours when deciding which source clauses to cite.
        effective_prompt = _ANALYSIS_PROMPT
        if doc_filter:
            effective_prompt = (
                f"Only use information from the document '{doc_filter}'."
                + effective_prompt
            )

        raw_response = await rag.aquery(
            question,
            param=QueryParam(
                mode="mix",
                only_need_context=False,
                top_k=24,
                chunk_top_k=12,
                enable_rerank=False,
                user_prompt=effective_prompt,
            ),
        )
        raw_str = raw_response if isinstance(raw_response, str) else str(raw_response)
        answer = re.split(r"\[ANALYSIS\]", raw_str, maxsplit=1)[0].strip()
        structured = _parse_analysis_block(raw_str)
        normalized_nodes = _normalize_graph_nodes(structured.get("graph_nodes_involved", []))
        validated_nodes = await _filter_graph_nodes_against_db(normalized_nodes, doc_filter=doc_filter, company_id=company_id)
        return {
            "answer": answer,
            "risk_level": structured["risk_level"],
            "source_clauses": structured["source_clauses"],
            "graph_nodes_involved": validated_nodes,
        }
    finally:
        await rag.finalize_storages()
