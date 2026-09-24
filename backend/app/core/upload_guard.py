"""Upload-guard helpers shared by tests and ``main.ingest`` (F2 hardening).

Pure stdlib + FastAPI HTTPException so router-level tests import this
without pulling heavy deps (neo4j / lightrag).
"""

from __future__ import annotations

from fastapi import HTTPException

MAX_PDF_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
ALLOWED_CONTENT_TYPES = frozenset({"application/pdf"})


def check_content_length_header(raw: str | None) -> None:
    """Pre-read reject: Content-Length above the cap -> 413."""
    if raw is None or not raw.strip().isdigit():
        return
    if int(raw.strip()) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds {MAX_PDF_BYTES} byte limit",
        )


def validate_upload(
    filename: str | None, content_type: str | None, content: bytes
) -> None:
    """Validate an already-read upload body.

    Raises 400 for wrong content-type / missing filename / empty body,
    413 when ``len(content)`` exceeds the cap, 422 when magic bytes are
    absent. JSON ``{detail}`` shape preserved via HTTPException.
    """
    if (content_type or "") not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")
    if not filename:
        raise HTTPException(
            status_code=400, detail="Uploaded file must include a filename"
        )
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds {MAX_PDF_BYTES} byte limit",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")
    if content[:5] != PDF_MAGIC:
        raise HTTPException(
            status_code=422,
            detail="Uploaded file is not a valid PDF (magic bytes mismatch)",
        )
