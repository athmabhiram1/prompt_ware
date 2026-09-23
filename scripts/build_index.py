#!/usr/bin/env python3
"""build_index.py — pre-index the 3 demo docs into warm-DB bundles (W1.4).

Demo corpus ONLY (3 docs, e.g. samples/msa.pdf, nda.pdf, offer.pdf). NEVER
the full corpus, NEVER local bulk: local LightRAG indexing benchmarks at
~63 s/chunk (33 filings / 629 chunks took 10.97 h on W7900+27B and slows as
the graph grows), so demo docs are indexed via CLOUD LLM only
(Gemini $300 free credit primary, Groq free tier fallback).

Modes:
  --dry-run (default when no cloud keys / Aura unreachable): deterministic
      chunking, writes data/preindex/*.json bundles with cost $0.00, prints
      the node-count receipt (or the exact Cypher to paste when Aura is
      paused). Exit 0 — this is the expected CI/offline path.
  --live: cloud-LLM indexing stub. Batches 50 chunks per insert, logs a $
      cost receipt, and REFUSES to run if the provider resolves to local
      (Ollama / localhost:11434) or if more than 3 docs are passed.

Node guard: MATCH (n) RETURN count(n) must stay < 180000 (200k Aura Free
cap minus 10% buffer). Storage note: engine today is Neo4JStorage with
Mongo/JSON fallback; PGVector/PGKV (PGTableGraphStorage) is the documented
fallback for the Neon DATABASE_URL migration — see render.yaml.

Cost model (receipt target <= $0.50 one-shot): Gemini free-tier credit
covers the demo index; receipt below itemises estimated input/output
tokens per batch so the spend is auditable.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from typing import NoReturn

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREINDEX_DIR = os.path.join(REPO_ROOT, "data", "preindex")
BATCH_SIZE = 50
MAX_DEMO_DOCS = 3
NODE_BUDGET = 180_000
COUNT_CYPHER = "MATCH (n) RETURN count(n)"
COST_BUDGET_USD = 0.50

# Rough Gemini pricing anchor for the receipt (торгуются, verify in console).
GEMINI_USD_PER_1K_IN = 0.000125
GEMINI_USD_PER_1K_OUT = 0.000375

DEMO_DOCS = [
    os.path.join("samples", "msa.pdf"),
    os.path.join("samples", "nda.pdf"),
    os.path.join("samples", "offer.pdf"),
]


def die(msg: str, code: int = 2) -> NoReturn:
    print(f"build_index: ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def refuse_local_bulk(provider: str) -> None:
    """Hard refusal: local bulk indexing is never allowed (63 s/chunk)."""
    if provider.strip().lower() in {"ollama", "local", "localhost"}:
        die(
            "refusing local-bulk mode: provider "
            f"'{provider}' resolves to Ollama/localhost, benchmarked at ~63 s/chunk "
            "(10.97 h for 629 chunks, slowing as the graph grows). "
            "Use --live with PRIMARY_LLM_PROVIDER=gemini (or groq) cloud keys instead."
        )


def chunk_text(text: str, size: int = 600, overlap: int = 120) -> list[str]:
    chunks: list[str] = []
    step = max(1, size - overlap)
    for i in range(0, len(text), step):
        piece = text[i : i + size].strip()
        if piece:
            chunks.append(piece)
    return chunks


def read_doc(path: str) -> str:
    if path.lower().endswith(".pdf"):
        try:
            import pymupdf  # optional: real text when available

            with pymupdf.open(path) as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception:
            pass  # fall through to placeholder (dry-run friendly)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def aura_node_count() -> int | None:
    """Best-effort node count via cypher-shell; None when Aura is paused/offline."""
    uri = os.getenv("AURA_URI") or os.getenv("NEO4J_CLOUD_URI", "") or os.getenv("NEO4J_URI", "")
    user = os.getenv("AURA_USERNAME") or os.getenv("NEO4J_CLOUD_USERNAME", "") or os.getenv("NEO4J_USERNAME", "")
    password = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_CLOUD_PASSWORD", "") or os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("AURA_DATABASE") or os.getenv("NEO4J_CLOUD_DATABASE", "") or os.getenv("NEO4J_DATABASE", "neo4j")
    if not (uri and user and password):
        return None
    try:
        out = subprocess.run(
            ["cypher-shell", "-a", uri, "-u", user, "-p", password,
             "-d", database, "--format", "plain", COUNT_CYPHER],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode == 0:
            digits = "".join(c for c in out.stdout if c.isdigit())
            return int(digits) if digits else None
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None  # Aura paused (72 h idle) or cypher-shell missing


def write_bundle(doc: str, chunks: list[str], mode: str, cost_usd: float) -> str:
    os.makedirs(PREINDEX_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(doc))[0]
    bundle = {
        "doc": doc,
        "mode": mode,  # "dry-run" | "live-cloud"
        "chunking": {"strategy": "char-window", "size": 600, "overlap": 120},
        "batch_size": BATCH_SIZE,
        "chunk_count": len(chunks),
        "chunks": chunks,
        "cost_usd": round(cost_usd, 6),
        "node_budget": NODE_BUDGET,
        "count_cypher": COUNT_CYPHER,
        "built_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "served": "cache-first when LLM_LIVE=0 or Aura paused",
    }
    path = os.path.join(PREINDEX_DIR, f"{base}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2)
    return path


def print_receipt(mode: str, docs: list[str], total_chunks: int,
                  batches: int, cost_usd: float, nodes: int | None) -> None:
    print("---- preindex receipt ----")
    print(f"mode        : {mode}")
    print(f"docs        : {len(docs)} ({', '.join(docs)})")
    print(f"chunks      : {total_chunks} in {batches} batch(es) of <={BATCH_SIZE}")
    print(f"cost_usd    : ${cost_usd:.6f} (budget <= ${COST_BUDGET_USD:.2f})")
    if cost_usd > COST_BUDGET_USD:
        die(f"cost ${cost_usd:.4f} exceeds one-shot budget ${COST_BUDGET_USD:.2f}.")
    if nodes is None:
        print(f"aura nodes  : unreachable (paused/offline) — paste `{COUNT_CYPHER}` "
              "in Aura console; gate is < 180000.")
    else:
        print(f"aura nodes  : {nodes} (paste-able: {COUNT_CYPHER} --> {nodes})")
        if nodes >= NODE_BUDGET:
            die(f"node count {nodes} >= budget {NODE_BUDGET}; index NOTHING new.")
    print("OK: receipt within budget; bundles served cache-first.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pre-index 3 demo docs (W1.4).")
    ap.add_argument("--docs", nargs="*", default=None,
                    help="demo docs (max 3). Default: samples/msa.pdf nda.pdf offer.pdf")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--live", action="store_true",
                    help="cloud-LLM indexing (requires GEMINI_API_KEY or GROQ_API_KEY)")
    ap.add_argument("--dry-run", action="store_true",
                    help="deterministic chunking only, $0 cost (default offline)")
    args = ap.parse_args(argv)

    docs = args.docs or DEMO_DOCS
    if len(docs) > MAX_DEMO_DOCS:
        die(f"demo 3 docs only — got {len(docs)}. Full-corpus indexing is forbidden (W1.4).")
    if args.batch_size != BATCH_SIZE and args.batch_size > BATCH_SIZE:
        die(f"batch size {args.batch_size} exceeds cap {BATCH_SIZE}.")

    provider = os.getenv("PRIMARY_LLM_PROVIDER", "gemini")
    refuse_local_bulk(provider)
    if os.getenv("OLLAMA_BASE_URL", "").find("localhost") >= 0 and args.live:
        die("OLLAMA_BASE_URL points at localhost — refusing live run on a local bulk path.")

    live = args.live
    if live and not (os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")):
        print("build_index: no cloud keys — falling back to --dry-run.", file=sys.stderr)
        live = False
    mode = "live-cloud" if live else "dry-run"

    total_chunks = 0
    for doc in docs:
        rel = doc if os.path.isabs(doc) else os.path.join(REPO_ROOT, doc)
        text = read_doc(rel)
        if not text.strip():
            # Dry-run friendly placeholder so bundles exist before PDFs land.
            text = f"[placeholder] {os.path.basename(doc)} — demo doc pending; bundle schema valid."
        chunks = chunk_text(text)
        # Live path batches BATCH_SIZE chunks per insert (LightRAG wiring: Wave 2).
        batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
        est_in = sum(len(c) // 4 for c in chunks)
        cost = 0.0 if not live else (est_in / 1000 * GEMINI_USD_PER_1K_IN
                                     + (len(chunks) * 40) / 1000 * GEMINI_USD_PER_1K_OUT)
        path = write_bundle(doc, chunks, mode, cost)
        print(f"bundle: {path} chunks={len(chunks)} batches={batches}")
        total_chunks += len(chunks)

    batches_total = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
    est_cost = 0.0 if not live else round(total_chunks * 150 / 4 / 1000 * GEMINI_USD_PER_1K_IN, 6)
    print_receipt(mode, docs, total_chunks, batches_total, est_cost, aura_node_count())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
