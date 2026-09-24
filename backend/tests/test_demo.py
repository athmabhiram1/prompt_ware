"""W4.1 demo cache — TDD gate (RED first, network blocked, LLM_LIVE=0).

Covers: GET /demo/{priya,msme,dpdp} serve frozen bundles with ZERO live
calls (socket.create_connection + getaddrinfo raise), full audit present
(risks + missing + obligations + brief refs), every brief bullet and QA
answer sentence carries a [doc p.N] cite, unknown id 404s, and
LLM_LIVE=1 still serves cache. No live LLM, no fixtures invented.
"""

import re
import socket
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import demo  # noqa: E402  (RED before demo.py exists)
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CITE_RE = re.compile(r"\[doc p\.\d+\]")

DEMO_IDS = ["priya", "msme", "dpdp"]


def _blocked(*args, **kwargs):
    raise RuntimeError("network blocked in demo test")


@pytest.fixture()
def blocked_network(monkeypatch):
    """Prove offline: any TCP dial or DNS lookup raises."""
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    return True


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(demo.router)
    return TestClient(app)


def test_demo_module_has_zero_live_imports():
    """demo.py must never import live LLM/graph SDKs (cache-only)."""
    source = Path(demo.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "llm_provider",
        "lightrag",
        "groq",
        "gemini",
        "httpx",
        "neo4j",
        "requests",
        "openai",
    ):
        assert forbidden not in source.lower(), f"live import leaked: {forbidden}"
    assert "served_from" in source or "cache" in source.lower()


def test_demo_priya_offline_full_audit(blocked_network, client):
    start = time.perf_counter()
    resp = client.get("/demo/priya")
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200, resp.text
    assert elapsed < 2.0, f"offline demo too slow: {elapsed:.2f}s"
    body = resp.json()

    audit = body["audit"]
    highs = [r for r in audit["risks"] if r["tier"] >= 4]
    assert len(highs) >= 3, f"priya needs >=3 HIGHs, got {len(highs)}"
    assert len(audit["contradictions"]) >= 1, "priya needs >=1 contradiction"
    assert len(audit["missing"]) >= 1
    assert len(audit["obligations"]) >= 1

    # every risk excerpt is a real span of the source text
    text = body["text"]
    for risk in audit["risks"]:
        assert text[risk["start"] : risk["end"]] == risk["excerpt"]
        assert risk["rule_id"].startswith("R")

    # every brief bullet claim carries a [doc p.X] cite — zero invented cites
    bullets = [
        ln
        for ln in body["brief"]["markdown"].splitlines()
        if ln.strip().startswith("-")
    ]
    assert len(bullets) >= 5
    for bullet in bullets:
        assert CITE_RE.search(bullet), bullet
    assert "not legal advice" in body["brief"]["markdown"].lower()

    # every QA answer sentence carries a cite
    assert len(body["qa"]) >= 1
    for pair in body["qa"]:
        assert pair["abstain"] is None or pair["answer"] is None
        if pair["answer"]:
            assert CITE_RE.search(pair["answer"]), pair["answer"]
            assert len(pair["citations"]) >= 1

    assert body["meta"]["served_from"] == "cache"
    assert body["meta"]["llm_live"] is False


@pytest.mark.parametrize("demo_id", DEMO_IDS)
def test_demo_all_ids_offline_200(blocked_network, client, demo_id):
    resp = client.get(f"/demo/{demo_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("demo_id", "title", "story", "text", "audit", "brief", "meta"):
        assert key in body, f"{demo_id} missing {key}"
    assert body["demo_id"] == demo_id
    assert body["meta"]["served_from"] == "cache"


def test_demo_unknown_id_404(blocked_network, client):
    resp = client.get("/demo/unknown-tenant")
    assert resp.status_code == 404


def test_demo_live_flag_still_serves_cache(blocked_network, client, monkeypatch):
    """LLM_LIVE=1 must NOT trigger live calls — cache wins for /demo/*."""
    monkeypatch.setenv("LLM_LIVE", "1")
    resp = client.get("/demo/priya")
    assert resp.status_code == 200, resp.text
    assert resp.json()["meta"]["served_from"] == "cache"


def test_demo_bundles_deterministic_on_disk():
    """Committed bundles exist; simplify cites are real spans."""
    repo = Path(demo.BUNDLE_DIR)
    assert repo.is_dir(), f"bundle dir missing: {repo}"
    for demo_id, bundle_file in demo.DEMO_TO_BUNDLE.items():
        path = repo / bundle_file
        assert path.is_file(), f"bundle missing: {path}"
        payload = demo.load_bundle(demo_id)
        text = payload["text"]
        for sent in payload["simplify"]["sentences"]:
            cite = sent["cite"]
            assert 0 <= cite["start"] < cite["end"] <= len(text)
