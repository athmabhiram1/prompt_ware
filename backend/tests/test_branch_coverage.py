"""Branch/edge coverage boost: health, upload_guard, redline, contradict, prompts, vec_pg."""

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_health_endpoints():
    from app.routers import health

    app = FastAPI()
    app.include_router(health.router)
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "env" in r.json()
    r2 = client.get("/ready")
    assert r2.status_code == 200
    assert "ready" in r2.json()
    assert "preindex" in r2.json()
    r3 = client.get("/health/db")
    assert r3.status_code == 200
    assert "checks" in r3.json()


def test_health_helpers_branch():
    from app.routers.health import _check_url_target, _scan_preindex, _tcp_reachable

    s = _check_url_target("", 5432)
    assert s.configured is False
    s2 = _check_url_target("not-a-url", 5432)
    assert s2.configured is True
    assert s2.reachable is False
    s3 = _check_url_target("postgresql://user:pass@127.0.0.1:59999/db", 5432)
    assert s3.configured is True
    ps = _scan_preindex()
    assert isinstance(ps.names, list)
    ok, ms, detail = _tcp_reachable("127.0.0.1", 59999, timeout_s=0.1)
    assert ok is False
    assert isinstance(ms, float)


def test_upload_guard_branches():
    from fastapi import HTTPException
    from app.core.upload_guard import (
        check_content_length_header,
        validate_upload,
        MAX_PDF_BYTES,
    )

    check_content_length_header(None)
    check_content_length_header("abc")
    check_content_length_header("  ")
    with pytest.raises(HTTPException) as e:
        check_content_length_header(str(MAX_PDF_BYTES + 1))
    assert e.value.status_code == 413
    with pytest.raises(HTTPException) as e:
        validate_upload(None, "application/pdf", b"%PDF-1.4 hello")
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        validate_upload("a.pdf", "text/plain", b"%PDF-")
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        validate_upload("a.pdf", "application/pdf", b"")
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        validate_upload("a.pdf", "application/pdf", b"NOTPDF")
    assert e.value.status_code == 422
    with pytest.raises(HTTPException) as e:
        validate_upload(
            "a.pdf", "application/pdf", b"%PDF-1.4\n" + b"x" * (MAX_PDF_BYTES + 1)
        )
    assert e.value.status_code == 413
    validate_upload("a.pdf", "application/pdf", b"%PDF-1.4 hello")


def test_redline_branches():
    from app.engine.redline import to_redlines_json, build_redline_docx

    deltas = [
        {
            "label": "added",
            "cites": [
                {"rule_id": "R01", "excerpt": "new", "start": 0, "end": 3, "side": "v2"}
            ],
        },
        {
            "label": "deleted",
            "cites": [
                {"rule_id": "R02", "excerpt": "old", "start": 0, "end": 3, "side": "v1"}
            ],
        },
        {"label": "cosmetic", "cites": []},
        {"label": "same", "cites": []},
        {
            "label": "modify",
            "cites": [
                {"rule_id": "R03", "excerpt": "a", "start": 0, "end": 1, "side": "v1"},
                {"rule_id": "R03", "excerpt": "b", "start": 0, "end": 1, "side": "v2"},
            ],
        },
    ]
    red = to_redlines_json(deltas)
    assert len(red.items) == 3
    assert red.items[0].action == "insert"
    assert red.items[1].action == "delete"
    docx_bytes = build_redline_docx(red)
    assert docx_bytes[:2] == b"PK"


def test_contradict_and_rules_edges():
    from app.engine.contradict import detect
    from app.engine.rules import scan

    c = detect("", findings=[])
    assert isinstance(c, list)
    r = scan("This is a plain agreement with rent 100000 and deposit 50000.")
    assert isinstance(r, list)


def test_prompts_and_vec_pg_edges():
    from app.rag.prompts import split_claims, protocol_errors, refuse

    claims = split_claims("answer is yes {cite:lease1:p1:0}.")
    assert len(claims) >= 1
    errs = protocol_errors(claims, known_ids={"lease1:p1:0"})
    assert isinstance(errs, list)
    msg = refuse("NO_EVIDENCE")
    assert isinstance(msg, str)
    from app.rag.vec_pg import resolve_backend, get_store

    assert resolve_backend() in ("pg", "memory")
    store = get_store()
    assert store is not None


def test_simplify_branches():
    from app.routers.simplify import SimplifyRequest, simplify_text, load_doc_text
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SimplifyRequest(level="99", text="hello")
    with pytest.raises(ValidationError):
        SimplifyRequest(lang="fr", text="hello")
    with pytest.raises(ValidationError):
        SimplifyRequest(text=None, doc_id=None, level="8")
    with pytest.raises(ValueError):
        simplify_text("   ", level="8")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        load_doc_text("no-such-doc-xyz-123")
    assert e.value.status_code == 404
    req = SimplifyRequest(text="hello world. second.", level=5)
    assert req.level == "5"
    req2 = SimplifyRequest(text="hello", level="pro")
    assert req2.level == "pro"
