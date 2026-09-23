import logging
import json
import socket
from pathlib import Path
from typing import Any

from neo4j import AsyncGraphDatabase

from llm_provider import get_active_rag_storage_dir
from neo4j_connection import Neo4jTarget, _candidate_targets

from app.core.redact import redact_pii


logger = logging.getLogger(__name__)

_async_driver = None
_active_target: Neo4jTarget | None = None


def _neo4j_reachable() -> bool:
    for target in _candidate_targets():
        if not target.password:
            continue
        try:
            host = target.uri.split("://")[-1].split(":")[0]
            port_str = target.uri.split("://")[-1].split(":")[-1] if ":" in target.uri.split("://")[-1] else "7687"
            port = int(port_str) if port_str.isdigit() else 7687
            with socket.create_connection((host, port), timeout=2):
                return True
        except Exception:
            continue
    return False


def _pg_configured() -> bool:
    """Env-only Postgres check (no bridge, no connections).

    The DATABASE_URL→POSTGRES_* bridge lives in lightrag_engine (which
    imports this module, so importing it back would be circular). A set
    DATABASE_URL alone counts as PG-configured here.
    """
    import os

    trio = all(os.getenv(k, "").strip() for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DATABASE"))
    return bool(trio or os.getenv("DATABASE_URL", "").strip())


def _graph_from_vdb_json(company_id: str) -> dict[str, Any]:
    """Read graph data from LightRAG's NanoVectorDB JSON files."""
    if company_id == "default_company":
        company_dir = get_active_rag_storage_dir()
    else:
        company_dir = get_active_rag_storage_dir() / company_id

    entities_path = company_dir / "vdb_entities.json"
    rels_path = company_dir / "vdb_relationships.json"

    nodes = []
    if entities_path.exists():
        try:
            with open(entities_path, encoding="utf-8") as f:
                data = json.load(f)
            records = data.get("data") if isinstance(data, dict) else data
            if isinstance(records, list):
                seen = set()
                for rec in records:
                    name = str(rec.get("entity_name", "")).strip()
                    if not name or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    nodes.append({"id": name, "label": name, "type": "entity"})
        except Exception as exc:
            logger.warning("Failed to read vdb_entities.json for %s: %s", redact_pii(company_id), redact_pii(exc))

    if not nodes:
        return _empty_graph()

    node_ids = {n["id"] for n in nodes}
    edges = []
    if rels_path.exists():
        try:
            with open(rels_path, encoding="utf-8") as f:
                data = json.load(f)
            records = data.get("data") if isinstance(data, dict) else data
            if isinstance(records, list):
                seen = set()
                for rec in records:
                    src = str(rec.get("src_id", "")).strip()
                    tgt = str(rec.get("tgt_id", "")).strip()
                    if not src or not tgt:
                        continue
                    pair = (src, tgt)
                    if pair in seen:
                        continue
                    seen.add(pair)
                    if src in node_ids and tgt in node_ids:
                        label = "RELATED_TO"
                        content = rec.get("content", "")
                        if content:
                            kw = content.split(",")[0].strip().upper().replace(" ", "_")[:50]
                            if kw:
                                label = kw
                        edges.append({"source": src, "target": tgt, "label": label})
        except Exception as exc:
            logger.warning("Failed to read vdb_relationships.json for %s: %s", redact_pii(company_id), redact_pii(exc))

    clean_nodes, clean_edges = _filter_hallucinated_nodes(nodes[:300], edges[:300], company_id)
    return {
        "nodes": clean_nodes,
        "edges": clean_edges,
        "stats": {"node_count": len(clean_nodes), "edge_count": len(clean_edges)},
    }


def _graph_from_networkx_json(company_id: str, doc_filter: str | None) -> dict[str, Any]:
    """Read graph data from LightRAG's NetworkX graphml file."""
    if company_id == "default_company":
        company_dir = get_active_rag_storage_dir()
    else:
        company_dir = get_active_rag_storage_dir() / company_id
    graphml = company_dir / "graph_chunk_entity_relation.graphml"
    if not graphml.exists():
        return _graph_from_vdb_json(company_id)
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(graphml)
        root = tree.getroot()
        ns = "http://graphml.graphdrawing.org/xmlns"

        # Build key-id → attr-name map
        key_map: dict[str, str] = {}
        for key_el in root.findall(f"{{{ns}}}key"):
            key_map[key_el.get("id", "")] = key_el.get("attr.name", "")

        nodes, edges = [], []
        graph_el = root.find(f"{{{ns}}}graph")
        if graph_el is None:
            return _empty_graph()

        for node_el in graph_el.findall(f"{{{ns}}}node"):
            node_id = node_el.get("id", "")
            # Prefer entity_id data element if present
            for data_el in node_el.findall(f"{{{ns}}}data"):
                if key_map.get(data_el.get("key", "")) == "entity_id":
                    node_id = data_el.text or node_id
                    break
            if node_id:
                nodes.append({"id": node_id, "label": node_id, "type": "entity"})

        node_ids = {n["id"] for n in nodes}
        for edge_el in graph_el.findall(f"{{{ns}}}edge"):
            src = edge_el.get("source", "")
            tgt = edge_el.get("target", "")
            label = "RELATED_TO"
            for data_el in edge_el.findall(f"{{{ns}}}data"):
                if key_map.get(data_el.get("key", "")) == "keywords":
                    kw = (data_el.text or "").split(",")[0].strip().upper().replace(" ", "_")
                    if kw:
                        label = kw
                    break
            if src in node_ids and tgt in node_ids:
                edges.append({"source": src, "target": tgt, "label": label})

        clean_nodes, clean_edges = _filter_hallucinated_nodes(nodes[:300], edges[:300], company_id)
        return {
            "nodes": clean_nodes,
            "edges": clean_edges,
            "stats": {"node_count": len(clean_nodes), "edge_count": len(clean_edges)},
        }
    except Exception as exc:
        logger.warning("Failed to read NetworkX graph for %s: %s", company_id, exc)
        return _graph_from_vdb_json(company_id)
def _safe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _chunk_ids_for_doc_filter(doc_filter: str | None, company_id: str) -> list[str]:
    filter_name = (doc_filter or "").strip().lower()
    if not filter_name:
        return []
    if _pg_configured():
        # PG-aware: chunk index lives in PG tables (T6 live query owns it),
        # not kv_store JSON — no local filter to build.
        return []

    if company_id == "default_company":
        company_dir = get_active_rag_storage_dir()
    else:
        company_dir = get_active_rag_storage_dir() / company_id
    full_docs = _safe_load_json(company_dir / "kv_store_full_docs.json")
    doc_status = _safe_load_json(company_dir / "kv_store_doc_status.json")
    matching_doc_ids: list[str] = []

    for doc_id, info in full_docs.items():
        if not isinstance(info, dict):
            continue
        file_path = str(info.get("file_path", "")).strip().lower()
        if not file_path:
            continue
        if filter_name in file_path or file_path.endswith(filter_name):
            matching_doc_ids.append(str(doc_id))

    chunk_ids: list[str] = []
    for doc_id in matching_doc_ids:
        status_data = doc_status.get(doc_id, {})
        if not isinstance(status_data, dict):
            continue
        chunks_list = status_data.get("chunks_list", [])
        if not isinstance(chunks_list, list):
            continue
        for chunk in chunks_list:
            chunk_id = str(chunk).strip()
            if chunk_id:
                chunk_ids.append(chunk_id)
    return chunk_ids


def _load_valid_entity_names(company_id: str) -> set[str]:
    """Load entity names from kv_store that were verified against source text.

    Returns a set of valid entity IDs (lowercased) that exist in the
    post-validation kv_store. Entities not in this set are LLM hallucinations
    that should be excluded from graph responses.

    PG-aware: with PG configured the validated entity list lives in PG
    tables, not kv_store JSON — returns empty (no filtering) and leaves
    enforcement to the T6 live path.
    """
    if _pg_configured():
        return set()
    if company_id == "default_company":
        storage_dir = get_active_rag_storage_dir()
    else:
        storage_dir = get_active_rag_storage_dir() / company_id
    full_entities_path = storage_dir / "kv_store_full_entities.json"
    if not full_entities_path.exists():
        return set()
    try:
        with open(full_entities_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return set()
    valid: set[str] = set()
    for doc_data in data.values():
        if not isinstance(doc_data, dict):
            continue
        names = doc_data.get("entity_names", [])
        if not isinstance(names, list):
            continue
        for name in names:
            raw = str(name).strip()
            if raw:
                valid.add(raw.lower())
    return valid

def _filter_hallucinated_nodes(nodes: list[dict], edges: list[dict], company_id: str) -> tuple[list[dict], list[dict]]:
    """Remove nodes whose entity_id doesn't appear in the validated kv_store.

    LightRAG's LLM-based entity extraction can hallucinate entities not
    present in the source document. This function filters those out by
    cross-referencing against the post-extraction validated entity list.
    """
    valid_names = _load_valid_entity_names(company_id)
    if not valid_names:
        return nodes, edges
    filtered_nodes = [n for n in nodes if str(n.get("id", "")).lower() in valid_names]
    filtered_ids = {n["id"] for n in filtered_nodes}
    filtered_edges = [
        e for e in edges
        if e.get("source") in filtered_ids and e.get("target") in filtered_ids
    ]
    return filtered_nodes, filtered_edges


def _empty_graph() -> dict[str, Any]:
    return {
        "nodes": [],
        "edges": [],
        "stats": {"node_count": 0, "edge_count": 0},
    }


async def _get_driver_and_target() -> tuple[Any, Neo4jTarget]:
    global _async_driver, _active_target

    if _async_driver is not None and _active_target is not None:
        return _async_driver, _active_target

    errors: list[str] = []
    for target in _candidate_targets():
        if not target.password:
            errors.append(f"{target.name}: missing password")
            continue
        try:
            candidate = AsyncGraphDatabase.driver(
                target.uri,
                auth=(target.username, target.password),
            )
            await candidate.verify_connectivity()
            _async_driver = candidate
            _active_target = target
            return _async_driver, _active_target
        except Exception as exc:
            errors.append(f"{target.name}: {exc}")

    raise RuntimeError("Unable to connect to Neo4j. " + "; ".join(errors))


async def get_full_graph() -> dict[str, Any]:
    return await get_full_graph_for_doc(None, company_id="base")


async def get_full_graph_for_doc(doc_filter: str | None, company_id: str = "base") -> dict[str, Any]:
    if _pg_configured():
        # PG-aware: graph rows live in PG tables (PGTableGraphStorage); the
        # live PG graph query is T6 key-gated work — file/Neo4j readers below
        # are N/A on the PG path. Neo4j fork stays for the non-PG path.
        logger.info("Graph fetch skipped (graph lives in Postgres, T6 owns live query)")
        return _empty_graph()
    if not _neo4j_reachable():
        return _graph_from_networkx_json(company_id, doc_filter)
    try:
        driver, target = await _get_driver_and_target()
        chunk_ids = _chunk_ids_for_doc_filter(doc_filter, company_id)
        use_doc_filter = bool((doc_filter or "").strip()) and len(chunk_ids) > 0

        cypher_label = "base" if company_id in {"default_company", "base"} else company_id

        node_records, _, _ = await driver.execute_query(
            f"""
            MATCH (n:`{cypher_label}`) WHERE n.entity_id IS NOT NULL
            AND (
              $use_doc_filter = false OR
              any(chunk in $chunk_ids WHERE toLower(coalesce(n.source_id, '')) CONTAINS toLower(chunk))
            )
            RETURN n.entity_id AS id
            LIMIT 300
            """,
            use_doc_filter=use_doc_filter,
            chunk_ids=chunk_ids,
            database_=target.database,
        )
        edge_records, _, _ = await driver.execute_query(
            f"""
            MATCH (n:`{cypher_label}`)-[r]->(m:`{cypher_label}`)
            WHERE n.entity_id IS NOT NULL AND m.entity_id IS NOT NULL
            AND (
              $use_doc_filter = false OR
              any(chunk in $chunk_ids WHERE toLower(coalesce(n.source_id, '')) CONTAINS toLower(chunk))
              OR
              any(chunk in $chunk_ids WHERE toLower(coalesce(m.source_id, '')) CONTAINS toLower(chunk))
            )
            RETURN n.entity_id AS source, m.entity_id AS target, type(r) AS label
            LIMIT 300
            """,
            use_doc_filter=use_doc_filter,
            chunk_ids=chunk_ids,
            database_=target.database,
        )

        nodes = [
            {"id": str(record["id"]), "label": str(record["id"]), "type": "entity"}
            for record in node_records
            if record.get("id")
        ]

        node_ids = {node["id"] for node in nodes}
        edges = [
            {
                "source": str(record["source"]),
                "target": str(record["target"]),
                "label": str(record["label"]),
            }
            for record in edge_records
            if record.get("source") and record.get("target") and record.get("label")
            and str(record["source"]) in node_ids
            and str(record["target"]) in node_ids
        ]

        clean_nodes, clean_edges = _filter_hallucinated_nodes(nodes, edges, company_id)
        return {
            "nodes": clean_nodes,
            "edges": clean_edges,
            "stats": {"node_count": len(clean_nodes), "edge_count": len(clean_edges)},
        }
    except Exception as exc:
        logger.exception("Failed to fetch full graph: %s", exc)
        return _empty_graph()


async def get_subgraph(node_ids: list[str]) -> dict[str, Any]:
    return await get_subgraph_for_doc(node_ids=node_ids, doc_filter=None, company_id="base")


async def get_subgraph_for_doc(node_ids: list[str], doc_filter: str | None, company_id: str = "base") -> dict[str, Any]:
    if not node_ids:
        return _empty_graph()
    if _pg_configured():
        # PG-aware: subgraph over PG tables is T6 live work (see full-graph note).
        logger.info("Subgraph fetch skipped (graph lives in Postgres, T6 owns live query)")
        return _empty_graph()
    if not _neo4j_reachable():
        # Find direct connections and 2-hop bridging nodes in NetworkX graph
        full = _graph_from_networkx_json(company_id, doc_filter)
        requested = set(node_ids)
        edges = []
        nodes_set = set(requested)
        
        # Build adjacency map
        adj = {}
        for e in full["edges"]:
            s, t = e["source"], e["target"]
            if s not in adj: adj[s] = set()
            if t not in adj: adj[t] = set()
            adj[s].add(t)
            adj[t].add(s)
            
        # Find intermediate nodes that connect at least two requested nodes
        inter_nodes = set()
        for node, neighbors in adj.items():
            if node in requested:
                continue
            req_neighbors = neighbors.intersection(requested)
            if len(req_neighbors) >= 2:
                inter_nodes.add(node)
                
        # Gather edges
        for e in full["edges"]:
            s, t = e["source"], e["target"]
            if s in requested and t in requested:
                edges.append(e)
            elif (s in requested and t in inter_nodes) or (t in requested and s in inter_nodes):
                edges.append(e)
                nodes_set.add(s)
                nodes_set.add(t)
                
        nodes = [n for n in full["nodes"] if n["id"] in nodes_set]
        return {"nodes": nodes, "edges": edges, "stats": {"node_count": len(nodes), "edge_count": len(edges)}}
    try:
        driver, target = await _get_driver_and_target()
        chunk_ids = _chunk_ids_for_doc_filter(doc_filter, company_id)
        use_doc_filter = bool((doc_filter or "").strip()) and len(chunk_ids) > 0

        cypher_label = "base" if company_id in {"default_company", "base"} else company_id

        # Bridging path query:
        # 1. Direct relationships between queried nodes
        # 2. Relationships to intermediate nodes that connect to at least one OTHER queried node
        records, _, _ = await driver.execute_query(
            f"""
            MATCH (n:`{cypher_label}`)-[r]-(m:`{cypher_label}`)
            WHERE n.entity_id IN $node_ids AND m.entity_id IN $node_ids AND n.entity_id < m.entity_id
            AND (
              $use_doc_filter = false OR
              any(chunk in $chunk_ids WHERE toLower(coalesce(n.source_id, '')) CONTAINS toLower(chunk))
            )
            RETURN n.entity_id AS src, m.entity_id AS tgt, type(r) AS label
            
            UNION
            
            MATCH (n:`{cypher_label}`)-[r]-(inter:`{cypher_label}`)
            WHERE n.entity_id IN $node_ids AND NOT inter.entity_id IN $node_ids
            AND (
              $use_doc_filter = false OR
              any(chunk in $chunk_ids WHERE toLower(coalesce(n.source_id, '')) CONTAINS toLower(chunk))
            )
            AND EXISTS {{
                MATCH (inter)-[]-(m:`{cypher_label}`)
                WHERE m.entity_id IN $node_ids AND m.entity_id <> n.entity_id
            }}
            RETURN n.entity_id AS src, inter.entity_id AS tgt, type(r) AS label
            """,
            node_ids=node_ids,
            use_doc_filter=use_doc_filter,
            chunk_ids=chunk_ids,
            database_=target.database,
        )

        nodes_set: set[str] = set()
        edges_set: set[tuple[str, str, str]] = set()

        for record in records:
            src = record.get("src")
            tgt = record.get("tgt")
            label = record.get("label")

            if src:
                nodes_set.add(str(src))
            if tgt:
                nodes_set.add(str(tgt))
            if src and tgt and label:
                edges_set.add((str(src), str(tgt), str(label)))

        nodes = [{"id": nid, "label": nid, "type": "entity"} for nid in sorted(nodes_set)]
        edges = [
            {"source": source, "target": tgt, "label": label}
            for source, tgt, label in sorted(edges_set)
        ]

        clean_nodes, clean_edges = _filter_hallucinated_nodes(nodes, edges, company_id)
        return {
            "nodes": clean_nodes,
            "edges": clean_edges,
            "stats": {"node_count": len(clean_nodes), "edge_count": len(clean_edges)},
        }
    except Exception as exc:
        logger.exception("Failed to fetch subgraph: %s", exc)
        return _empty_graph()


def clean_entity_description(desc: str) -> str:
    if not desc:
        return ""
    import re
    parts = re.split(r"(?i)<sep>", desc)
    seen = set()
    cleaned_parts = []
    for part in parts:
        p = part.strip()
        if not p:
            continue
        p_lower = p.lower()
        if p_lower not in seen:
            seen.add(p_lower)
            if not p.endswith((".", "!", "?", ";")):
                p += "."
            cleaned_parts.append(p)
    return "\n\n".join(cleaned_parts)


async def get_node_details(node_id: str) -> dict[str, Any]:
    if not node_id:
        return {"id": node_id, "label": node_id, "description": "", "type": "entity", "source_files": []}

    try:
        driver, target = await _get_driver_and_target()

        records, _, _ = await driver.execute_query(
            """
            MATCH (n) WHERE n.entity_id = $node_id
            RETURN n.entity_id AS id,
                   n.description AS description,
                   n.entity_type AS entity_type,
                   n.source_id AS source_id
            LIMIT 1
            """,
            node_id=node_id,
            database_=target.database,
        )

        if not records:
            return {"id": node_id, "label": node_id, "description": "", "type": "entity", "source_files": []}

        record = records[0]
        description = clean_entity_description(str(record.get("description") or ""))
        entity_type = str(record.get("entity_type") or "entity").strip()
        source_id = str(record.get("source_id") or "").strip()

        # source_id is comma-separated chunk IDs; surface the first few as hints
        source_hints = [s.strip() for s in source_id.split(",") if s.strip()][:3]

        return {
            "id": node_id,
            "label": node_id,
            "description": description,
            "type": entity_type,
            "source_files": source_hints,
        }
    except Exception as exc:
        logger.exception("Failed to fetch node details for %s: %s", redact_pii(node_id), redact_pii(exc))
        return {"id": node_id, "label": node_id, "description": "", "type": "entity", "source_files": []}