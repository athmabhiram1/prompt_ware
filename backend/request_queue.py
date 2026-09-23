import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import redis.asyncio as aioredis


logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class QueuedTask:
    id: str
    queue_name: str
    payload: dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    retry_delay: float = 1.0


_redis_pool: aioredis.Redis | None = None
_workers: dict[str, asyncio.Task] = {}


def _get_redis_url() -> str:
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD", "")
    db = os.getenv("REDIS_DB", "0")
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.Redis.from_url(
            _get_redis_url(),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


async def enqueue(
    queue_name: str,
    payload: dict[str, Any],
    priority: TaskPriority = TaskPriority.NORMAL,
    max_retries: int = 3,
) -> str:
    redis = await get_redis()
    task = QueuedTask(
        id=f"{queue_name}:{int(time.time() * 1000)}:{os.urandom(4).hex()}",
        queue_name=queue_name,
        payload=payload,
        priority=priority,
        max_retries=max_retries,
    )
    key = f"queue:{queue_name}"
    await redis.rpush(key, json.dumps({
        "id": task.id,
        "payload": task.payload,
        "priority": task.priority.value,
        "max_retries": task.max_retries,
        "retry_count": 0,
        "enqueued_at": time.time(),
    }))
    logger.info("Enqueued task=%s queue=%s", task.id, queue_name)
    return task.id


async def dequeue(queue_name: str, timeout: float = 5.0) -> dict[str, Any] | None:
    redis = await get_redis()
    key = f"queue:{queue_name}"
    result = await redis.blpop(key, timeout=int(timeout))
    if result is None:
        return None
    _, raw = result
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to decode task from queue=%s", queue_name)
        return None


async def requeue(queue_name: str, task_data: dict[str, Any]) -> None:
    retry_count = task_data.get("retry_count", 0) + 1
    max_retries = task_data.get("max_retries", 3)
    if retry_count > max_retries:
        logger.error("Task %s exceeded max retries (%d), discarding", task_data.get("id"), max_retries)
        dead_key = f"queue:{queue_name}:dead"
        redis = await get_redis()
        await redis.rpush(dead_key, json.dumps({**task_data, "retry_count": retry_count, "failed_at": time.time()}))
        return
    task_data["retry_count"] = retry_count
    delay = task_data.get("retry_delay", 1.0) * (2 ** (retry_count - 1))
    await asyncio.sleep(delay)
    redis = await get_redis()
    key = f"queue:{queue_name}"
    await redis.rpush(key, json.dumps(task_data))
    logger.info("Requeued task=%s attempt=%d/%d delay=%.1fs", task_data.get("id"), retry_count, max_retries, delay)


async def start_worker(
    queue_name: str,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
    poll_interval: float = 1.0,
) -> asyncio.Task:
    async def _run() -> None:
        logger.info("Worker started queue=%s poll_interval=%.1fs", queue_name, poll_interval)
        while True:
            try:
                task_data = await dequeue(queue_name, timeout=poll_interval)
                if task_data is None:
                    continue
                try:
                    await handler(task_data)
                except Exception as exc:
                    logger.error("Handler failed for task=%s: %s", task_data.get("id"), exc)
                    await requeue(queue_name, task_data)
            except asyncio.CancelledError:
                logger.info("Worker cancelled queue=%s", queue_name)
                break
            except Exception as exc:
                logger.error("Worker error queue=%s: %s", queue_name, exc)
                await asyncio.sleep(5)

    task = asyncio.create_task(_run())
    _workers[queue_name] = task
    return task


async def stop_worker(queue_name: str) -> None:
    task = _workers.pop(queue_name, None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def stop_all_workers() -> None:
    for name in list(_workers.keys()):
        await stop_worker(name)
    await close_redis()


async def queue_size(queue_name: str) -> int:
    redis = await get_redis()
    return await redis.llen(f"queue:{queue_name}")
