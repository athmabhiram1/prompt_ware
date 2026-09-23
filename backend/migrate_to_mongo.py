"""Migrate existing local rag_storage data to MongoDB Atlas.

Reads all JSON files from the current rag_storage namespace directory and
seeds the corresponding MongoDB collections so the system works on a new
machine with just the .env configured.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

NS_NAMES = {
    "kv_store_full_docs": "full_docs",
    "kv_store_text_chunks": "text_chunks",
    "kv_store_full_entities": "full_entities",
    "kv_store_full_relations": "full_relations",
    "kv_store_entity_chunks": "entity_chunks",
    "kv_store_relation_chunks": "relation_chunks",
    "kv_store_llm_response_cache": "llm_response_cache",
    "kv_store_doc_status": "doc_status",
    "vdb_chunks": "chunks_vdb",
    "vdb_entities": "entities_vdb",
    "vdb_relationships": "relationships_vdb",
}


def get_rag_base_dir() -> Path:
    # Match the logic in llm_provider.get_active_rag_storage_dir
    base = Path(__file__).resolve().parent / "rag_storage"
    # Determine namespace dir the same way
    embed_provider = os.getenv("EMBED_PROVIDER", "gemini").strip().lower()
    if embed_provider == "gemini":
        model = "gemini-embedding-2-preview"
        dim = "3072"
    elif embed_provider == "ollama":
        model = os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding").strip().lower()
        dim = os.getenv("OLLAMA_EMBED_DIM", "768").strip()
    else:
        model = embed_provider
        dim = "768"
    safe_model = model.replace("-", "_").replace(":", "_").replace("/", "_")
    return base / f"{embed_provider}_{safe_model}_{dim}"


def load_json(path: Path) -> dict:
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main() -> None:
    uri = os.getenv("MONGO_URI", "").strip()
    database_name = os.getenv("MONGO_DATABASE", "nyayamitra").strip()
    if not uri:
        print("ERROR: MONGO_URI is not set. Add it to .env first.")
        sys.exit(1)

    # Late import so the script doesn't require pymongo unless used
    from pymongo import MongoClient

    ns_dir = get_rag_base_dir()
    if not ns_dir.is_dir():
        print(f"ERROR: namespace directory not found: {ns_dir}")
        sys.exit(1)

    client = MongoClient(uri)
    db = client[database_name]

    # ---------------------------------------------------------------
    # 1. Base-level files (workspace = "")
    # ---------------------------------------------------------------
    print(f"\nScanning base level: {ns_dir}")
    for filename, namespace in NS_NAMES.items():
        path = ns_dir / filename
        if not path.exists():
            # Try .json extension
            path = ns_dir / f"{filename}.json"
        if not path.exists():
            # Some files may already be .json
            path = ns_dir / f"{filename}"
            if not path.suffix:
                path = ns_dir / f"{filename}.json"
                if not path.exists():
                    continue

        data = load_json(path)
        if not data:
            continue

        collection = db[namespace]
        total = len(data)
        inserted = 0
        # Detect format: NanoVectorDB uses dict{k:v} or {data:[...]}
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            # NanoVectorDB format: {"embedding_dim": N, "data": [{__id__: ..., vector: ..., ...}], "matrix": "..."}
            for entry in data["data"]:
                if not isinstance(entry, dict):
                    continue
                doc_id = entry.pop("__id__", None) or entry.pop("id", None)
                if not doc_id:
                    continue
                doc = dict(entry)
                doc["_id"] = doc_id
                try:
                    collection.replace_one({"_id": doc_id}, doc, upsert=True)
                    inserted += 1
                except Exception as e:
                    print(f"  Error inserting {namespace}/{doc_id}: {e}")
        else:
            # Standard dict format: {key: {fields...}}
            for key, value in data.items():
                if not isinstance(value, dict):
                    continue  # skip metadata fields like embedding_dim
                doc = dict(value)
                doc["_id"] = key
                try:
                    collection.replace_one({"_id": key}, doc, upsert=True)
                    inserted += 1
                except Exception as e:
                    print(f"  Error inserting {namespace}/{key}: {e}")

        print(f"  {namespace}: {inserted}/{total} documents (total items in file: {total})")

    # ---------------------------------------------------------------
    # 2. Per-company workspace directories
    # ---------------------------------------------------------------
    for company_dir in sorted(ns_dir.iterdir()):
        if not company_dir.is_dir():
            continue
        company_id = company_dir.name
        print(f"\nScanning workspace: {company_id}")

        for filename, namespace in NS_NAMES.items():
            path = company_dir / filename
            if not path.exists():
                path = company_dir / f"{filename}.json"
            if not path.exists():
                path = company_dir / f"{filename}"
                if not path.suffix:
                    path = company_dir / f"{filename}.json"
                    if not path.exists():
                        continue

            data = load_json(path)
            if not data:
                continue

            collection_name = f"{company_id}_{namespace}"
            collection = db[collection_name]
            total = len(data)
            inserted = 0

            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                for entry in data["data"]:
                    if not isinstance(entry, dict):
                        continue
                    doc_id = entry.pop("__id__", None) or entry.pop("id", None)
                    if not doc_id:
                        continue
                    doc = dict(entry)
                    doc["_id"] = doc_id
                    try:
                        collection.replace_one({"_id": doc_id}, doc, upsert=True)
                        inserted += 1
                    except Exception as e:
                        print(f"  Error inserting {collection_name}/{doc_id}: {e}")
            else:
                for key, value in data.items():
                    if not isinstance(value, dict):
                        continue
                    doc = dict(value)
                    doc["_id"] = key
                    try:
                        collection.replace_one({"_id": key}, doc, upsert=True)
                        inserted += 1
                    except Exception as e:
                        print(f"  Error inserting {collection_name}/{key}: {e}")

            print(f"  {collection_name}: {inserted}/{total} documents migrated")

    # Create vector search indexes for VDB collections
    def _infer_vector_dim() -> int:
        for coll_name in db.list_collection_names():
            if any(coll_name.endswith(s) for s in ["chunks_vdb", "entities_vdb", "relationships_vdb"]):
                doc = db[coll_name].find_one({"vector": {"$exists": True}})
                if doc and isinstance(doc.get("vector"), list):
                    return len(doc["vector"])
        return 4096

    vec_dim = _infer_vector_dim()
    print(f"\nCreating vector search indexes (dim={vec_dim})...")
    vdb_suffixes = ["chunks_vdb", "entities_vdb", "relationships_vdb"]
    for coll_name in db.list_collection_names():
        if not any(coll_name.endswith(s) for s in vdb_suffixes):
            continue
        collection = db[coll_name]
        try:
            existing = list(collection.list_search_indexes())
            if not any(idx["name"] == "vector_knn_index" for idx in existing):
                collection.create_search_index({
                    "name": "vector_knn_index",
                    "type": "vectorSearch",
                    "definition": {
                        "fields": [{
                            "type": "vector",
                            "numDimensions": vec_dim,
                            "path": "vector",
                            "similarity": "cosine",
                        }]
                    },
                })
                print(f"  Created vector index on {coll_name}")
            else:
                print(f"  Vector index exists on {coll_name}")
        except Exception as e:
            print(f"  Skip vector index on {coll_name}: {e}")

    client.close()
    print("\nDone. All data migrated to MongoDB Atlas.")


if __name__ == "__main__":
    main()
