"""Controller agent for dynamic LangGraph search routing."""

from __future__ import annotations

from typing import Any, Mapping

from app.agents.base_execution import BaseExecutionAgent


class ControllerAgent(BaseExecutionAgent):
    """Decides the next graph action from accumulated runtime state."""

    def __init__(self, *, max_retries: int) -> None:
        self._max_retries = max_retries

    async def act(self, state: Mapping[str, Any]) -> dict[str, Any]:
        next_action = self._decide_next_action(state)
        decision_trace = list(state.get("decision_trace", []))
        decision_trace.append(
            {
                "step": "controller_node",
                "action": next_action,
                "retry_count": state.get("retry_count", 0),
                "match_quality": state.get("match_quality", ""),
                "current_entity": state.get("current_entity", ""),
            }
        )
        return {
            "current_step": "controller_node",
            "next_action": next_action,
            "decision_trace": decision_trace,
            "last_observation": {
                "controller_action": next_action,
                "retry_count": state.get("retry_count", 0),
                "match_quality": state.get("match_quality", ""),
            },
        }

    def _decide_next_action(self, state: Mapping[str, Any]) -> str:
        final_structured = state.get("final_structured_query")
        plan_steps = set(final_structured.execution_plan.steps) if final_structured else set()
        if not state.get("structured_query"):
            return "parse_query_node"
        if state.get("tool_request") and not state.get("tool_result"):
            return "tool_execution_node"
        if state.get("tool_result"):
            return "product_matching_node"
        if state.get("response") is not None:
            return "response_node"
        if not state.get("normalized_item"):
            return "normalization_node"
        if not state.get("unified_product"):
            return "product_matching_node"
        if not state.get("match_quality"):
            return "match_quality_node"
        if state.get("match_quality") == "strong":
            if not state.get("ranking_result"):
                return "ranking_node"
            if "deal_detection_node" in plan_steps and state.get("deal_result") is None:
                return "deal_detection_node"
            return "response_node"
        if state.get("retry_count", 0) < int(state.get("max_retries", self._max_retries)):
            return "enrichment_node"
        unified_product = state.get("unified_product")
        if unified_product and getattr(unified_product, "platforms", []):
            if not state.get("ranking_result"):
                return "ranking_node"
            if "deal_detection_node" in plan_steps and state.get("deal_result") is None:
                return "deal_detection_node"
            return "response_node"
        return "response_node"
