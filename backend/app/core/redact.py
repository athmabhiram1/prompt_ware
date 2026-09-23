"""PII redaction for log lines (F2 hardening).

Keep raw document text, entity names, and identifier-like tokens out of
logs: every helper returns a string safe to pass to ``logger.*``.
No real PII fixtures are committed; tests use synthetic tokens only.
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]"),  # PAN-like: ABCDE1234F
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),  # Aadhaar-like digit runs
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email-like
    re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"),  # phone-like
)


def redact_pii(value: object, max_len: int = 200) -> str:
    """Return a log-safe rendering of ``value``.

    Identifier-like tokens become ``[REDACTED]``; outputs longer than
    ``max_len`` are truncated with a ``[REDACTED:truncated]`` marker so
    raw excerpts never reach logs in full.
    """
    text = value if isinstance(value, str) else str(value)
    for pattern in _PATTERNS:
        text = pattern.sub(REDACTED, text)
    if len(text) > max_len:
        return text[:max_len] + "...[REDACTED:truncated]"
    return text
