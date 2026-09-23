#!/usr/bin/env python3
"""render_worker.py — Render worker entrypoint (W1.4).

Heartbeat + queue-depth monitor against the Render Key Value broker using
the existing request_queue.py helpers. Real ingest handling stays
in-process (BackgroundTasks fallback in request_queue.py, started from
main.py lifespan) until traffic justifies a dedicated drain — on a
512 MB instance do NOT add heavy handlers here.

Uses only REDIS_HOST / REDIS_PORT / REDIS_PASSWORD / REDIS_DB.
If the broker is unreachable, logs and sleeps (in-process asyncio queue
mode covers handling); never crash-loops.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../backend")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("render_worker")

QUEUES = ("ingest", "index")
POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "30"))


async def once() -> None:
    try:
        from request_queue import queue_size
    except Exception as exc:  # redis lib / broker missing
        log.warning("queue module unavailable (%s); in-process asyncio mode active.", exc)
        return
    for q in QUEUES:
        try:
            log.info("queue=%s depth=%s", q, await queue_size(q))
        except Exception as exc:
            log.warning("broker unreachable for queue=%s (%s); retrying next poll.", q, exc)


async def main() -> None:
    log.info("nyayamitra worker online (poll=%ss, broker=%s:%s).",
             POLL_SECONDS, os.getenv("REDIS_HOST", "localhost"), os.getenv("REDIS_PORT", "6379"))
    while True:
        await once()
        await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
