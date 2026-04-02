"""Compiled LangGraph search execution runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from app.data.models import EvaluationFrame, MatchingDiagnostics
from app.orchestrator.state import SearchGraphState

if TYPE_CHECKING:
    from app.orchestrator.pipeline import AgentPipeline


def build_search_execution_graph(pipeline: "AgentPipeline"):
    """Build the compiled search execution graph owned by AgentPipeline."""

    async def parse_query_node(state: SearchGraphState) -> SearchGraphState:
        final_structured = await pipeline.parse_query(state.get("user_query", ""))
        return {
            "final_structured_query": final_structured,
            "structured_query": final_structured.structured_query,
            "candidate_entities": pipeline._build_candidate_entities(final_structured),
            "ranking_preferences": dict(final_structured.constraints.ranking_preference_weights),
            "budget_limit": (final_structured.constraints.budget or {}).get("amount"),
        }

    async def normalization_node(state: SearchGraphState) -> SearchGraphState:
        structured_query = state["structured_query"]
        candidates = state.get("candidate_entities") or [structured_query.product]
        current_index = min(state.get("current_path_index", 0), max(len(candidates) - 1, 0))
        current_entity = candidates[current_index] if candidates else structured_query.product
        normalized_item = await pipeline._normalization_agent.run(current_entity)
        return {
            "candidate_entities": candidates,
            "current_path_index": current_index,
            "current_entity": current_entity,
            "selected_path": f"path-{current_index}",
            "normalized_item": normalized_item,
        }

    async def product_matching_node(state: SearchGraphState) -> SearchGraphState:
        structured_query = state["structured_query"]
        normalized_item = state["normalized_item"]
        unified_product = await pipeline._product_agent.run(structured_query, normalized_item)
        unified_product = pipeline._apply_market_signal_adjustments(
            unified_product,
            normalized_item,
            state.get("market_signals", {}),
        )
        diagnostics = unified_product.diagnostics
        path_history = list(state.get("path_history", []))
        path_history.append(
            {
                "path_id": state.get("selected_path", "path-0"),
                "entity": state.get("current_entity", normalized_item.canonical_name),
                "result_count": len(unified_product.platforms),
                "quality_score": diagnostics.quality_score,
                "matched_via": diagnostics.matched_via,
            }
        )
        return {
            "unified_product": unified_product,
            "diagnostics": diagnostics,
            "tool_trace": [attempt.model_dump() for attempt in diagnostics.tool_attempts],
            "path_history": path_history,
        }

    async def match_quality_node(state: SearchGraphState) -> SearchGraphState:
        diagnostics = state.get("diagnostics") or MatchingDiagnostics()
        unified_product = state.get("unified_product")
        products = unified_product.platforms if unified_product else []
        if not products:
            match_quality = "empty"
        elif (
            diagnostics.approximate_match
            or diagnostics.quality_score < pipeline._matching_quality_threshold
            or len(products) < pipeline._min_high_quality_results
        ):
            match_quality = "weak"
        else:
            match_quality = "strong"
        return {"match_quality": match_quality}

    async def enrichment_node(state: SearchGraphState) -> SearchGraphState:
        final_structured = state["final_structured_query"]
        normalized_item = state.get("normalized_item")
        diagnostics = (state.get("diagnostics") or MatchingDiagnostics()).model_copy(deep=True)
        diagnostics.fallback_trace.append("graph_enrichment")
        extra_candidates = []
        if normalized_item:
            extra_candidates.extend(normalized_item.possible_variants)
            if normalized_item.category:
                extra_candidates.extend(pipeline._category_candidates(normalized_item.category))
        extra_candidates.extend(final_structured.ambiguity.candidate_entities or [])
        extra_candidates.extend(final_structured.fallback.alternatives or [])
        extra_candidates.extend(
            variant
            for entity in final_structured.normalized_entities.entities
            for variant in entity.possible_variants
        )
        updated_candidates = pipeline._sanitize_candidate_entities(
            [*state.get("candidate_entities", []), *extra_candidates]
        )
        next_index = min(
            state.get("current_path_index", 0) + 1,
            max(len(updated_candidates) - 1, 0),
        )
        return {
            "candidate_entities": updated_candidates,
            "current_path_index": next_index,
            "retry_count": state.get("retry_count", 0) + 1,
            "diagnostics": diagnostics,
        }

    async def ranking_node(state: SearchGraphState) -> SearchGraphState:
        ranking_result = await pipeline._ranking_agent.run(
            state["unified_product"],
            ranking_preferences=state.get("ranking_preferences"),
        )
        ranking_result = pipeline._apply_budget_optimization(
            ranking_result.model_copy(deep=True),
            state.get("budget_limit"),
        )
        return {
            "ranked_products": ranking_result,
            "ranking_result": ranking_result,
        }

    async def deal_detection_node(state: SearchGraphState) -> SearchGraphState:
        final_structured = state["final_structured_query"]
        deal_result = await pipeline._deal_agent.run(state["unified_product"])
        if "deal_detection_node" not in final_structured.execution_plan.steps:
            deal_result.deals = []
            deal_result.trending_deals = []
        return {
            "deals": deal_result,
            "deal_result": deal_result,
        }

    async def response_node(state: SearchGraphState) -> SearchGraphState:
        final_structured = state["final_structured_query"]
        response = pipeline._builder.build_search_response(dict(state))
        evaluation_result = await pipeline._evaluation_agent.run(final_structured, response)
        selected_path = state.get("selected_path", "path-0")
        retry_count = state.get("retry_count", 0)

        final_structured.learning_signals.retry_count = retry_count
        final_structured.learning_signals.evaluation_notes.extend(evaluation_result.correction_suggestions)
        final_structured.learning_signals.evaluation_notes.append(f"selected_path:{selected_path}")
        final_structured.evaluation_history.append(
            EvaluationFrame(
                iteration=retry_count,
                path_id=selected_path,
                quality_score=evaluation_result.quality_score,
                failures=evaluation_result.failure_signals,
                corrections=evaluation_result.correction_suggestions,
            )
        )
        for policy_item in final_structured.failure_policies:
            if policy_item.failure_type in (evaluation_result.failure_signals or []):
                policy_item.applied = True
        for path in final_structured.candidate_paths:
            if path.path_id == selected_path:
                path.selected = True
                path.status = "selected"
                path.quality_score = evaluation_result.quality_score
            elif path.path_id in {entry["path_id"] for entry in state.get("path_history", [])}:
                path.selected = False
                path.status = "evaluated"

        await pipeline._query_logger.run("evaluation", evaluation_result.model_dump())
        pipeline._decorate_search_response(
            response=response,
            final_structured=final_structured,
            retry_count=retry_count,
            selected_path=selected_path,
            match_quality=state.get("match_quality", "empty"),
            tool_trace=state.get("tool_trace", []),
            path_history=state.get("path_history", []),
        )
        if evaluation_result.success:
            await pipeline._learning_loop.learn_from_success(final_structured)
        else:
            await pipeline._learning_loop.learn_from_outcome(final_structured, success=False)
        await pipeline._emit_search_event(final_structured, response, selected_path)
        return {
            "response": response,
            "evaluation_result": evaluation_result,
            "final_structured_query": final_structured,
        }

    def route_entry(state: SearchGraphState) -> str:
        return "parse_query_node" if not state.get("structured_query") else "normalization_node"

    def route_match_quality(state: SearchGraphState) -> str:
        if state.get("match_quality") == "strong":
            return "ranking_node"
        if state.get("retry_count", 0) < state.get(
            "max_retries",
            pipeline._max_enrichment_retry_attempts,
        ):
            return "enrichment_node"
        unified_product = state.get("unified_product")
        if unified_product and unified_product.platforms:
            return "ranking_node"
        return "response_node"

    graph = StateGraph(SearchGraphState)
    graph.add_node("parse_query_node", parse_query_node)
    graph.add_node("normalization_node", normalization_node)
    graph.add_node("product_matching_node", product_matching_node)
    graph.add_node("match_quality_node", match_quality_node)
    graph.add_node("enrichment_node", enrichment_node)
    graph.add_node("ranking_node", ranking_node)
    graph.add_node("deal_detection_node", deal_detection_node)
    graph.add_node("response_node", response_node)

    graph.add_conditional_edges(
        START,
        route_entry,
        {
            "parse_query_node": "parse_query_node",
            "normalization_node": "normalization_node",
        },
    )
    graph.add_edge("parse_query_node", "normalization_node")
    graph.add_edge("normalization_node", "product_matching_node")
    graph.add_edge("product_matching_node", "match_quality_node")
    graph.add_conditional_edges(
        "match_quality_node",
        route_match_quality,
        {
            "ranking_node": "ranking_node",
            "enrichment_node": "enrichment_node",
            "response_node": "response_node",
        },
    )
    graph.add_edge("enrichment_node", "product_matching_node")
    graph.add_edge("ranking_node", "deal_detection_node")
    graph.add_edge("deal_detection_node", "response_node")
    graph.add_edge("response_node", END)
    return graph.compile()
