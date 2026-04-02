"""Base abstractions for graph-executed runtime agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class BaseExecutionAgent(ABC):
    """Runtime interface for state-driven LangGraph agents."""

    @abstractmethod
    async def act(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Read current graph state and return updated keys."""
