"""Base abstractions for graph-executed runtime agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class BaseExecutionAgent(ABC):
    """Runtime interface for state-driven LangGraph agents."""

    @abstractmethod
    async def act(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Run agent-specific logic against graph state and return updated keys.

        Implementations should inspect the current state snapshot, perform their
        execution logic, and return only the keys that changed. Runtime agents
        are expected to update observability fields such as `current_step` and
        `last_observation` when they execute.
        """
