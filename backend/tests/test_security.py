"""F2 security hardening gate — TDD (RED first, no live deps).

Covers the 5 reviewer patches:
1. Upload guard: >10MB -> 413, non-%PDF- magic -> 422 (via app.core.upload_guard,
   the same helper wired into POST /ingest in main.py).
2. Pydantic max_length: qa question<=2000, simplify text<=50000,
   compare a/b<=50000, brief text<=20000 (+ main.py QueryRequest source check).
3. Rate-limit wiring: main.py source + requirements pin checks.
4. PII redaction: redact_pii masks digit runs / phone-like / long excerpts.
5. Security headers: middleware adds nosniff + DENY + CSP (via TestClient).

No live LLM, no heavy imports (never imports main — neo4j/lightrag absent).
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]


def test_qa_question_overlong_rejected() -> None:
    from app.routers.qa import QaRequest

    with pytest.raises(ValidationError):
        QaRequest(question="x" * 2001, doc_id="d1")


def test_qa_question_100kb_rejected() -> None:
    from app.routers.qa import QaRequest

    with pytest.raises(ValidationError):
        QaRequest(question="y" * 100_000, doc_id="d1")


def test_simplify_text_overlong_rejected() -> None:
    from app.routers.simplify import SimplifyRequest

    with pytest.raises(ValidationError):
        SimplifyRequest(text="z" * 50_001, level="8")


def test_compare_sides_overlong_rejected() -> None:
    from app.routers.compare import CompareRequest

    with pytest.raises(ValidationError):
        CompareRequest(a="a" * 50_001, b="ok")
    with pytest.raises(ValidationError):
        CompareRequest(a="ok", b="b" * 50_001)


def test_brief_text_overlong_rejected() -> None:
    from app.routers.brief import BriefRequest

    with pytest.raises(ValidationError):
        BriefRequest(text="w" * 20_001)


def test_main_query_request_has_max_length() -> None:
    src = (BACKEND / "main.py").read_text(encoding="utf-8")
    block = src[src.index("class QueryRequest") : src.index("class SourceClause")]
    assert "max_length" in block, "QueryRequest.question needs Field(max_length=2000)"


def test_upload_oversize_rejected_413() -> None:
    from fastapi import HTTPException

    from app.core.upload_guard import MAX_PDF_BYTES, validate_upload

    assert MAX_PDF_BYTES == 10 * 1024 * 1024
    big = b"%PDF-1.4\n" + b"x" * (MAX_PDF_BYTES + 1)
    with pytest.raises(HTTPException) as exc:
        validate_upload("big.pdf", "application/pdf", big)
    assert exc.value.status_code == 413


def test_upload_bad_magic_rejected_422() -> None:
    from fastapi import HTTPException

    from app.core.upload_guard import validate_upload

    with pytest.raises(HTTPException) as exc:
        validate_upload("note.pdf", "application/pdf", b"NOT A PDF AT ALL....")
    assert exc.value.status_code == 422


def test_upload_wrong_content_type_rejected() -> None:
    from fastapi import HTTPException

    from app.core.upload_guard import validate_upload

    with pytest.raises(HTTPException) as exc:
        validate_upload("evil.exe", "application/x-msdownload", b"%PDF-1.4\nok")
    assert exc.value.status_code in (400, 422)


def test_upload_valid_small_pdf_accepted() -> None:
    from app.core.upload_guard import validate_upload

    validate_upload("lease.pdf", "application/pdf", b"%PDF-1.4\n%ok\n")


def test_redact_pii_masks_digit_runs_and_phones() -> None:
    from app.core.redact import redact_pii

    raw = "PAN ABCDE1234F call 9876543210 id 1234-5678-9012"
    out = redact_pii(raw)
    assert "[REDACTED]" in out
    assert "9876543210" not in out
    assert "ABCDE1234F" not in out


def test_redact_pii_truncates_long_excerpts() -> None:
    from app.core.redact import redact_pii

    out = redact_pii("x" * 500, max_len=120)
    assert len(out) <= 120 + 30
    assert "[REDACTED" in out  # truncation marker present


def test_security_headers_middleware_present() -> None:
    from app.core.security_headers import SecurityHeadersMiddleware

    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in resp.headers


def test_main_wires_rate_limiter() -> None:
    src = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "slowapi" in src
    assert "limiter.limit" in src or 'limit("30/minute")' in src or "30/minute" in src


def test_requirements_pins_slowapi() -> None:
    reqs = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    assert "slowapi==" in reqs, "slowapi must be pinned (slowapi==x.y.z)"


def test_vercel_json_has_security_headers() -> None:
    import json

    cfg = json.loads((REPO / "vercel.json").read_text(encoding="utf-8"))
    headers = cfg.get("headers", [])
    assert headers, "vercel.json needs a headers array"
    blob = json.dumps(headers)
    assert "Content-Security-Policy" in blob
    assert "nosniff" in blob
    assert "DENY" in blob
