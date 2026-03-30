"""Queue System: background job workers.

Flow: Scheduler → Queue → Workers → Jobs

Used for:
- Scheduled scraper execution
- Price history updates
- Price alert notifications
- Background cache warming

README
------
Keeps heavy operations out of the request path to ensure low latency.
Uses asyncio-based background tasks (upgradeable to Celery/RQ in production).
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class JobType(str, Enum):
    scrape_prices = "scrape_prices"
    update_price_history = "update_price_history"
    send_price_alert = "send_price_alert"
    warm_cache = "warm_cache"


class Job:
    """Represents a background job."""

    def __init__(
        self,
        job_type: JobType,
        payload: Dict[str, Any],
        handler: Callable[..., Coroutine],
    ) -> None:
        self.job_type = job_type
        self.payload = payload
        self.handler = handler
        self.status: str = "queued"
        self.error: Optional[str] = None

    async def execute(self) -> None:
        try:
            self.status = "running"
            await self.handler(**self.payload)
            self.status = "completed"
        except Exception as exc:
            self.status = "failed"
            self.error = str(exc)
            logger.error("Job %s failed: %s", self.job_type, exc)


class JobQueue:
    """Simple asyncio-based in-memory job queue.

    In production, replace with Celery + Redis/RabbitMQ or RQ.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._running = False

    async def start(self, num_workers: int = 2) -> None:
        """Start background worker coroutines."""
        self._running = True
        for i in range(num_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(task)
        logger.info("JobQueue started with %d workers.", num_workers)

    async def stop(self) -> None:
        """Gracefully stop all workers."""
        self._running = False
        for task in self._workers:
            task.cancel()
        self._workers.clear()
        logger.info("JobQueue stopped.")

    async def enqueue(self, job: Job) -> None:
        """Add a job to the queue."""
        await self._queue.put(job)
        logger.debug("Enqueued job: %s", job.job_type)

    async def _worker(self, name: str) -> None:
        logger.debug("Worker %s started.", name)
        while self._running:
            try:
                job: Job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                logger.debug("Worker %s processing job %s", name, job.job_type)
                await job.execute()
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Worker %s unexpected error: %s", name, exc)


# ------------------------------------------------------------------
# Built-in job handlers (stub implementations for now)
# ------------------------------------------------------------------


async def handle_scrape_prices(platform: str, category: str) -> None:
    """Stub: trigger price scraping for a platform/category."""
    logger.info("Scraping prices for %s / %s", platform, category)
    await asyncio.sleep(0)  # placeholder for real scraper call


async def handle_update_price_history(entity: str) -> None:
    """Stub: update price history records for an entity."""
    logger.info("Updating price history for %s", entity)
    await asyncio.sleep(0)


async def handle_send_price_alert(user_id: str, entity: str, threshold: float) -> None:
    """Stub: send price alert notification to user."""
    logger.info("Sending price alert to user %s for %s below ₹%.2f", user_id, entity, threshold)
    await asyncio.sleep(0)


async def handle_warm_cache(queries: list) -> None:
    """Stub: pre-warm cache for popular queries."""
    logger.info("Warming cache for %d queries.", len(queries))
    await asyncio.sleep(0)


# Module-level singleton
_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    global _queue
    if _queue is None:
        _queue = JobQueue()
    return _queue
