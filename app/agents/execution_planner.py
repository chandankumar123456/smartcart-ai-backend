"""Adaptive execution planner for multi-intent orchestration."""

from __future__ import annotations

import uuid

from app.data.models import (
    CandidateExecutionPath,
    Constraints,
    ExecutionGraph,
    ExecutionNode,
    ExecutionPlan,
    IntentResult,
    QueryIntent,
    UserContext,
)

_BASE_PATH_CONFIDENCE = 0.5
_MAX_PATH_CONFIDENCE_BOOST = 0.45
_PATH_CONFIDENCE_INCREMENT = 0.1


class ExecutionPlannerAgent:
    async def run(
        self,
        intent_result: IntentResult,
        constraints: Constraints,
        user_context: UserContext,
        candidate_entities: list[str],
    ) -> tuple[ExecutionPlan, ExecutionGraph, list[CandidateExecutionPath]]:
        primary = intent_result.intent
        secondary = set(intent_result.secondary_intents)
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        nodes: list[ExecutionNode] = [
            ExecutionNode(node_id="match", operation="product_matching"),
            ExecutionNode(node_id="rank", operation="ranking", depends_on=["match"]),
            ExecutionNode(node_id="deals", operation="deal_detection", depends_on=["rank"]),
        ]
        edges = [
            {"from": "match", "to": "rank"},
            {"from": "rank", "to": "deals"},
        ]
        adaptive_flags = {
            "skip_deals": "cheap" in constraints.preferences,
            "skip_ranking": primary == QueryIntent.exploratory and intent_result.confidence < 0.6,
            "personalized_weights": bool(user_context.preferences or user_context.dietary_patterns),
        }
        if adaptive_flags["skip_deals"]:
            nodes = [n for n in nodes if n.node_id != "deals"]
            edges = [e for e in edges if e["to"] != "deals"]
        if adaptive_flags["skip_ranking"]:
            nodes = [n for n in nodes if n.node_id != "rank"]
            edges = [e for e in edges if e["to"] != "rank" and e["from"] != "rank"]

        candidate_paths = []
        for idx, candidate in enumerate(candidate_entities[:3]):
            confidence_penalty = min(_MAX_PATH_CONFIDENCE_BOOST, idx * _PATH_CONFIDENCE_INCREMENT)
            candidate_paths.append(
                CandidateExecutionPath(
                    path_id=f"path-{idx}",
                    entity_candidate=candidate,
                    confidence=_BASE_PATH_CONFIDENCE + (_MAX_PATH_CONFIDENCE_BOOST - confidence_penalty),
                )
            )

        if primary == QueryIntent.recipe and QueryIntent.cart_optimization in secondary:
            nodes.append(
                ExecutionNode(
                    node_id="recipe",
                    operation="recipe_generation",
                    condition="intent_recipe",
                )
            )
            nodes.append(
                ExecutionNode(
                    node_id="optimize",
                    operation="cart_optimization",
                    depends_on=["recipe"],
                )
            )
            edges.extend([{"from": "recipe", "to": "optimize"}])
        elif primary == QueryIntent.recipe:
            nodes.append(
                ExecutionNode(
                    node_id="recipe",
                    operation="recipe_generation",
                    condition="intent_recipe",
                )
            )
        elif primary == QueryIntent.cart_optimization:
            nodes.append(
                ExecutionNode(
                    node_id="optimize",
                    operation="cart_optimization",
                    condition="intent_cart",
                )
            )

        graph = ExecutionGraph(
            graph_id=f"graph-{plan_id}",
            nodes=nodes,
            edges=edges,
        )
        plan = ExecutionPlan(
            mode="graph",
            plan_id=plan_id,
            steps=[n.operation for n in nodes],
            entry_nodes=[n.node_id for n in nodes if not n.depends_on],
            terminal_nodes=[n.node_id for n in nodes if n.node_id not in {e["from"] for e in edges}],
            adaptive_flags=adaptive_flags,
            reason=f"Graph planned for {primary.value} with {len(candidate_paths)} ambiguity paths",
        )
        return plan, graph, candidate_paths
