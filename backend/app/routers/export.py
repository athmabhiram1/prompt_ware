"""W3.1 GET /export.ics — RFC5545 VEVENT+VALARM calendar export.

Pattern: ``ics`` lib ``createEvents`` (Context7 ``/adamgibbons/ics`` —
``setAlarm`` VALARM block). Server builds the string manually (no new dep)
so CI stays light; frontend ``Calendar.tsx`` mirrors via ``lib/brief.ts``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response

DISCLAIMER = "Information, not legal advice — verify with advocate"

router = APIRouter(tags=["export"])

_DEFAULT_DTSTART = "20260430T100000"
_DEFAULT_TITLE = "NyayaMitra deadline reminder"


def _stamp_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _clean(value: str) -> str:
    return " ".join(value.split()).replace(",", ";")[:200] or _DEFAULT_TITLE


def build_ics(
    job_id: str = "brief",
    title: str = _DEFAULT_TITLE,
    dtstart: str = _DEFAULT_DTSTART,
    dtend: str = "",
) -> str:
    """Build a minimal RFC5545 calendar with one VEVENT + VALARM."""
    start = (dtstart or _DEFAULT_DTSTART).strip()
    end = (dtend or "").strip() or (
        start[:8] + "T110000" if len(start) >= 8 else _DEFAULT_DTSTART
    )
    uid = f"{(job_id or 'brief').strip() or 'brief'}@nyayamitra"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NyayaMitra//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_stamp_now()}",
        f"DTSTART:{start}",
        f"DTEND:{end}",
        f"SUMMARY:{_clean(title)}",
        f"DESCRIPTION:{_clean(title)} — {DISCLAIMER}",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:" + _clean(title),
        "TRIGGER:-PT24H",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


@router.get("/export.ics")
def get_ics(
    job_id: str = "brief",
    title: str = _DEFAULT_TITLE,
    dtstart: str = _DEFAULT_DTSTART,
    dtend: str = "",
) -> Response:
    """Serve the deadline calendar (imports to Google Calendar)."""
    try:
        body = build_ics(job_id=job_id, title=title, dtstart=dtstart, dtend=dtend)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=body,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=nyayamitra.ics"},
    )
