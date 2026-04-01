"""Query Logging Agent."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class QueryLoggingAgent:
    """Structured query-stage logger for observability."""

    def __init__(self) -> None:
        self._stage_counts: Dict[str, int] = {}
        self._failure_counts: Dict[str, int] = {}

    async def run(self, stage: str, payload: Dict[str, Any]) -> None:
        self._stage_counts[stage] = self._stage_counts.get(stage, 0) + 1
        if payload.get("used") is True and stage == "fallback":
            self._failure_counts["fallback_used"] = self._failure_counts.get("fallback_used", 0) + 1
        if payload.get("allowed") is False and stage == "domain_guard":
            self._failure_counts["domain_blocked"] = self._failure_counts.get("domain_blocked", 0) + 1
        logger.info("[QUERY_LOG] stage=%s payload=%s", stage, payload)

    async def get_learning_snapshot(self) -> Dict[str, Dict[str, int]]:
        return {
            "stage_counts": dict(self._stage_counts),
            "failure_counts": dict(self._failure_counts),
        }
