"""Query Logging Agent."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class QueryLoggingAgent:
    """Structured query-stage logger for observability."""

    async def run(self, stage: str, payload: Dict[str, Any]) -> None:
        logger.info("[QUERY_LOG] stage=%s payload=%s", stage, payload)
