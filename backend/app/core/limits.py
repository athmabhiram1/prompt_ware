"""Central slowapi limiter (F2 hardening).

Single instance imported by ``main.py`` and the qa/simplify/compare/brief
routers so every guarded endpoint shares one 30/min/IP budget source.
Falls back to a no-op shim when slowapi is absent so boot never breaks.
"""

from __future__ import annotations

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    _HAVE_SLOWAPI = True
except Exception:  # pragma: no cover - boot must never break
    _HAVE_SLOWAPI = False

    class _NoOpLimiter:  # type: ignore[no-redef]
        def limit(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN202
            def wrap(fn):  # noqa: ANN001, ANN202
                return fn

            return wrap

    limiter = _NoOpLimiter()  # type: ignore[assignment]

RATE_30_PER_MIN = "30/minute"
