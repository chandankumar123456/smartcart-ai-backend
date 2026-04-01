"""Lightweight scheduler to enqueue periodic scraper jobs."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Optional

from app.core.config import get_settings
from app.queue.worker import Job, JobType, get_job_queue, handle_scrape_prices

logger = logging.getLogger(__name__)
_settings = get_settings()


class ScraperScheduler:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if not _settings.scraper_enabled or self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="smartcart-scraper-scheduler")
        logger.info("Scraper scheduler started (interval=%s min)", _settings.scraper_interval_minutes)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        queue = get_job_queue()
        interval = max(5, int(_settings.scraper_interval_minutes)) * 60
        while self._running:
            await queue.enqueue(
                Job(
                    job_type=JobType.scrape_prices,
                    payload={"platform": "blinkit", "category": "all"},
                    handler=handle_scrape_prices,
                )
            )
            await asyncio.sleep(interval)


_scheduler: Optional[ScraperScheduler] = None


def get_scraper_scheduler() -> ScraperScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ScraperScheduler()
    return _scheduler
