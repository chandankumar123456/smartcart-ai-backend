"""Distributed agent coordination primitives."""

from __future__ import annotations

from typing import Any, Dict, List


class AgentCoordinationNetwork:
    def __init__(self) -> None:
        self._signals: Dict[str, Dict[str, Any]] = {}
        self._influence_log: List[Dict[str, Any]] = []

    def share(self, sender: str, target: str, key: str, value: Any) -> None:
        bucket = self._signals.setdefault(target, {})
        bucket[key] = value
        self._influence_log.append({"sender": sender, "target": target, "key": key})

    def request(self, agent: str, key: str, default: Any = None) -> Any:
        return self._signals.get(agent, {}).get(key, default)

    def trace(self) -> Dict[str, Any]:
        return {"signals": self._signals, "influence_log": self._influence_log}


_network: AgentCoordinationNetwork | None = None


def get_coordination_network() -> AgentCoordinationNetwork:
    global _network
    if _network is None:
        _network = AgentCoordinationNetwork()
    return _network
