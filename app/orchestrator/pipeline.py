"""LangGraph-based Orchestrator.

Controls the full multi-agent pipeline:
  User Query → QueryUnderstandingAgent → (recipe | product pipeline)
            → ProductMatchingAgent → RankingAgent → DealDetectionAgent
            → Response

README
------
Core pipeline engine. Uses a directed graph (LangGraph-style StateGraph) to
manage agent execution flow. Falls back to a simple sequential runner if
LangGraph is not installed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.agents.constraint_extraction import ConstraintExtractionAgent
from app.agents.constraint_optimizer import ConstraintOptimizerAgent
from app.agents.deal_detection import DealDetectionAgent
from app.agents.domain_guard import DomainGuardAgent
from app.agents.ambiguity_reasoning import AmbiguityReasoningAgent
from app.agents.evaluation import EvaluationAgent
from app.agents.entity_extraction import EntityExtractionAgent
from app.agents.execution_planner import ExecutionPlannerAgent
from app.agents.intent_detection import IntentDetectionAgent
from app.agents.language_processing import LanguageProcessingAgent
from app.agents.fallback import FallbackAgent
from app.agents.normalization import NormalizationAgent
from app.agents.output_formatter import OutputFormatterAgent
from app.agents.product_matching import ProductMatchingAgent
from app.agents.query_logging import QueryLoggingAgent
from app.agents.query_understanding import QueryUnderstandingAgent
from app.agents.ranking import RankingAgent
from app.agents.recipe import RecipeAgent
from app.agents.synonym_memory import SynonymMemoryAgent
from app.agents.user_context import UserContextAgent
from app.data.layer import get_products_for_entity
from app.data.models import (
    CartItem,
    CartOptimizationResult,
    CartPlatformGroup,
    FailurePolicy,
    FinalStructuredQuery,
    FinalResponse,
    NormalizedItem,
    QueryFilters,
    QueryMetadata,
    QueryIntent,
    LearningSignals,
    EvaluationResult,
    EvaluationFrame,
    PlatformEvent,
    PlatformEventType,
    QueryConstraints,
    RecipeResult,
    StructuredItem,
    StructuredQuery,
)
from app.coordination.network import get_coordination_network
from app.events.platform_events import get_platform_event_intelligence
from app.memory.shared import get_shared_memory
from app.learning.feedback import LearningLoop
from app.llm.manager import LLMManager, get_llm_manager
from app.response.builder import ResponseBuilder

logger = logging.getLogger(__name__)
_MAX_REASONING_RETRY_ATTEMPTS = 3
_MAX_CANDIDATE_ENTITIES = 3
_MIN_OPTIMIZATION_SCORE = 0.2
_GLOBAL_OPTIMIZATION_DELIVERY_WEIGHT = 0.2
_DEFAULT_DELIVERY_MINUTES = 30.0
_MAX_DELIVERY_MINUTES = 90.0


class AgentPipeline:
    """Sequential multi-agent pipeline (LangGraph-compatible design).

    Each step receives the accumulated state dict and returns updated state.
    This mirrors LangGraph's StateGraph pattern and can be trivially wrapped
    in a real LangGraph graph if the package is available.
    """

    def __init__(self, llm_manager: Optional[LLMManager] = None) -> None:
        llm = llm_manager or get_llm_manager()
        self._synonym_memory = SynonymMemoryAgent()
        self._language_agent = LanguageProcessingAgent()
        self._intent_agent = IntentDetectionAgent()
        self._entity_agent = EntityExtractionAgent()
        self._constraint_agent = ConstraintExtractionAgent()
        self._domain_guard_agent = DomainGuardAgent()
        self._ambiguity_agent = AmbiguityReasoningAgent()
        self._execution_planner_agent = ExecutionPlannerAgent()
        self._evaluation_agent = EvaluationAgent()
        self._user_context_agent = UserContextAgent()
        self._constraint_optimizer = ConstraintOptimizerAgent()
        self._fallback_agent = FallbackAgent()
        self._formatter_agent = OutputFormatterAgent()
        self._query_logger = QueryLoggingAgent()
        self._query_agent = QueryUnderstandingAgent(llm)
        self._product_agent = ProductMatchingAgent()
        self._normalization_agent = NormalizationAgent(llm, synonym_memory=self._synonym_memory)
        self._ranking_agent = RankingAgent()
        self._deal_agent = DealDetectionAgent()
        self._recipe_agent = RecipeAgent(llm)
        self._builder = ResponseBuilder()
        self._learning_loop = LearningLoop(self._synonym_memory)
        self._platform_events = get_platform_event_intelligence()
        self._shared_memory = get_shared_memory()
        self._coordination = get_coordination_network()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def parse_query(self, query: str) -> FinalStructuredQuery:
        """Build fully structured query before execution layer."""
        state: Dict[str, Any] = {"raw_query": query}
        clean_query = await self._language_agent.run(query)
        await self._query_logger.run("language_processing", clean_query.model_dump())
        intent_result = await self._intent_agent.run(clean_query)
        await self._query_logger.run("intent_detection", intent_result.model_dump())
        raw_entities = await self._entity_agent.run(clean_query, intent_result)
        await self._query_logger.run("entity_extraction", raw_entities.model_dump())
        normalized_entities = await self._normalization_agent.run_entities(raw_entities)
        await self._query_logger.run("normalization", normalized_entities.model_dump())
        constraints = await self._constraint_agent.run(clean_query)
        await self._query_logger.run("constraint_extraction", constraints.model_dump())
        domain_guard = await self._domain_guard_agent.run(clean_query, intent_result)
        await self._query_logger.run("domain_guard", domain_guard.model_dump())
        ambiguity = await self._ambiguity_agent.run(intent_result, raw_entities, normalized_entities)
        await self._query_logger.run("ambiguity_reasoning", ambiguity.model_dump())
        fallback = await self._fallback_agent.run(normalized_entities, intent_result.intent)
        await self._query_logger.run("fallback", fallback.model_dump())
        user_context = await self._user_context_agent.run(clean_query)
        await self._query_logger.run("user_context", user_context.model_dump())
        execution_plan, execution_graph, candidate_paths = await self._execution_planner_agent.run(
            intent_result=intent_result,
            constraints=constraints,
            user_context=user_context,
            candidate_entities=ambiguity.candidate_entities or raw_entities.candidate_entities,
        )
        await self._query_logger.run("execution_planning", execution_plan.model_dump())
        ranking_adjustments = self._constraint_optimizer.derive_weights(
            constraints.ranking_preference_weights,
            constraints.preferences,
            user_context.preferences,
        )
        constraints.ranking_preference_weights = ranking_adjustments
        failure_policies = [
            FailurePolicy(failure_type="vague_query", action="branch_candidates", retries_allowed=2),
            FailurePolicy(failure_type="constraint_violation", action="rebalance_budget", retries_allowed=2),
            FailurePolicy(failure_type="missing_entities", action="fallback_search", retries_allowed=1),
            FailurePolicy(failure_type="external_failure", action="graceful_degrade", retries_allowed=1),
        ]
        learning_signals = LearningSignals(
            normalization_reinforced=[e.canonical_name for e in normalized_entities.entities if e.canonical_name],
            failed_matches=list(normalized_entities.unresolved_entities),
            ranking_adjustments=ranking_adjustments,
            constraint_violations=list(constraints.conflict_notes),
            evaluation_notes=[],
            retry_count=0,
        )

        primary_normalized_entity = normalized_entities.entities[0] if normalized_entities.entities else None
        primary_entity = primary_normalized_entity.canonical_name if primary_normalized_entity else ""
        category = primary_normalized_entity.category if primary_normalized_entity else "general"
        structured_query = StructuredQuery(
            product=primary_entity or clean_query.normalized_text or query,
            filters=QueryFilters(
                max_price=(constraints.budget or {}).get("amount") if constraints.budget else None,
                category=category,
            ),
            intent=intent_result.intent,
            normalized_query=clean_query.normalized_text,
            items=[
                StructuredItem(
                    name=primary_entity or "grocery items",
                    category=category or "general",
                    attributes={"preferences": constraints.preferences},
                )
            ],
            constraints=QueryConstraints(
                budget=constraints.budget,
                servings=constraints.servings,
                preferences=constraints.preferences,
            ),
            metadata=QueryMetadata(confidence=intent_result.confidence, notes=intent_result.notes),
            raw_query=query,
        )
        final_structured = await self._formatter_agent.run(
            clean_query=clean_query,
            intent_result=intent_result,
            raw_entities=raw_entities,
            normalized_entities=normalized_entities,
            constraints=constraints,
            domain_guard=domain_guard,
            ambiguity=ambiguity,
            fallback=fallback,
            execution_plan=execution_plan,
            execution_graph=execution_graph,
            candidate_paths=candidate_paths,
            user_context=user_context,
            learning_signals=learning_signals,
            evaluation_history=[],
            failure_policies=failure_policies,
            structured_query=structured_query,
        )
        strategy = await self._shared_memory.get_strategy("recommendation_signals")
        final_structured.platform_signals = {
            "recommendation_signals": strategy.get("recommendation_signals", {}),
            "analytics_signals": strategy.get("analytics_signals", {}),
            "forecast_signals": strategy.get("forecast_signals", {}),
        }
        if strategy.get("recommendation_signals", {}).get("preferences"):
            for pref in strategy["recommendation_signals"]["preferences"]:
                if pref not in final_structured.user_context.preferences:
                    final_structured.user_context.preferences.append(pref)
        if strategy.get("forecast_signals", {}).get("predicted_needs"):
            for need in strategy["forecast_signals"]["predicted_needs"]:
                if need not in final_structured.user_context.predicted_needs:
                    final_structured.user_context.predicted_needs.append(need)
        self._coordination.share("planner", "ranking", "ranking_preferences", constraints.ranking_preference_weights)
        final_structured.coordination_trace = self._coordination.trace()
        await self._query_logger.run("output_formatter", final_structured.model_dump())
        await self._learning_loop.learn_from_success(final_structured)
        state["final_structured_query"] = final_structured
        return final_structured

    async def run_search(self, final_structured: FinalStructuredQuery) -> FinalResponse:
        """Execute search only from finalized structured intelligence."""
        logger.debug("[ENTRY] endpoint=/search type=search_execution_structured")
        state: Dict[str, Any] = {"raw_query": final_structured.clean_query.text}
        state["final_structured_query"] = final_structured
        state["structured_query"] = final_structured.structured_query

        if not final_structured.domain_guard.allowed:
            return self._builder.build_domain_guard_response(state)

        sq: StructuredQuery = state["structured_query"]
        if sq.intent == QueryIntent.unsupported:
            return self._builder.build_unsupported_response(state)
        if any(n.operation == "recipe_generation" for n in final_structured.execution_graph.nodes):
            response = await self.run_recipe(final_structured.clean_query.text)
            if any(n.operation == "cart_optimization" for n in final_structured.execution_graph.nodes):
                response.metadata["secondary_intents"] = [i.value for i in final_structured.intent_result.secondary_intents]
                response.metadata["execution_plan"] = final_structured.execution_plan.model_dump()
            return response
        policy = await self._learning_loop.load_policy(final_structured.clean_query.normalized_text)
        market_signals = await self._shared_memory.get_strategy("market_signals")
        self._coordination.share("memory", "matching", "market_signals", market_signals)
        ranking_boost = self._coordination.request("ranking", "ranking_preferences", {})
        if policy.get("ranking_adjustments"):
            final_structured.constraints.ranking_preference_weights = self._constraint_optimizer.derive_weights(
                policy.get("ranking_adjustments", {}),
                final_structured.constraints.preferences,
                final_structured.user_context.preferences,
            )
        if ranking_boost:
            merged = dict(final_structured.constraints.ranking_preference_weights)
            merged.update({k: float(v) for k, v in ranking_boost.items()})
            final_structured.constraints.ranking_preference_weights = merged
        candidate_entities = [c.entity_candidate for c in final_structured.candidate_paths] or [sq.product]
        if final_structured.normalized_entities.entities:
            primary = final_structured.normalized_entities.entities[0]
            candidate_entities = [primary.canonical_name, *candidate_entities]
        candidate_entities = self._sanitize_candidate_entities(candidate_entities)

        best_response: Optional[FinalResponse] = None
        best_eval = EvaluationResult(success=False, should_retry=True, quality_score=0.0)
        best_path = ""
        retries = 0
        while retries < _MAX_REASONING_RETRY_ATTEMPTS:
            path_results: List[tuple[str, FinalResponse, EvaluationResult]] = []
            for idx, entity in enumerate(candidate_entities):
                path_id = f"path-{idx}"
                path_state = dict(state)
                normalized = await self._normalization_agent.run(entity)
                path_state["normalized_item"] = normalized
                path_state["unified_product"] = await self._product_agent.run(sq, normalized)
                live_entity = market_signals.get(normalized.canonical_name, {}) if isinstance(market_signals, dict) else {}
                if live_entity.get("in_stock") is False:
                    alt_candidates = [c for c in candidate_entities if c != entity]
                    if alt_candidates:
                        normalized = await self._normalization_agent.run(alt_candidates[0])
                        path_state["normalized_item"] = normalized
                        path_state["unified_product"] = await self._product_agent.run(sq, normalized)
                if live_entity.get("price") is not None:
                    live_price = float(live_entity.get("price"))
                    for p in path_state["unified_product"].platforms:
                        if p.normalized_name == normalized.canonical_name.lower().strip():
                            p.price = min(p.price, live_price)
                path_state["ranking_result"] = await self._ranking_agent.run(
                    path_state["unified_product"],
                    ranking_preferences=final_structured.constraints.ranking_preference_weights,
                )
                budget_limit = (final_structured.constraints.budget or {}).get("amount")
                path_state["ranking_result"] = self._apply_budget_optimization(
                    path_state["ranking_result"],
                    budget_limit,
                )
                path_state["deal_result"] = await self._deal_agent.run(path_state["unified_product"])
                if "deal_detection" not in final_structured.execution_plan.steps:
                    path_state["deal_result"].deals = []
                    path_state["deal_result"].trending_deals = []
                candidate_response = self._builder.build_search_response(path_state)
                candidate_eval = await self._evaluation_agent.run(final_structured, candidate_response)
                final_structured.evaluation_history.append(
                    EvaluationFrame(
                        iteration=retries,
                        path_id=path_id,
                        quality_score=candidate_eval.quality_score,
                        failures=candidate_eval.failure_signals,
                        corrections=candidate_eval.correction_suggestions,
                    )
                )
                path_results.append((path_id, candidate_response, candidate_eval))

            chosen = max(path_results, key=lambda x: x[2].quality_score)
            best_path, best_response, best_eval = chosen
            if not best_eval.should_retry:
                break
            retries += 1
            final_structured.learning_signals.retry_count = retries
            final_structured.learning_signals.evaluation_notes.extend(best_eval.correction_suggestions)
            if "poor_match_quality" in best_eval.failure_signals:
                candidate_entities = self._sanitize_candidate_entities(
                    candidate_entities + (final_structured.ambiguity.candidate_entities or [])
                )
            if "constraint_violation" in best_eval.failure_signals:
                final_structured.constraints.ranking_preference_weights = self._constraint_optimizer.derive_weights(
                    final_structured.constraints.ranking_preference_weights,
                    ["cheap", *final_structured.constraints.preferences],
                    final_structured.user_context.preferences,
                )

        for path in final_structured.candidate_paths:
            path.selected = path.path_id == best_path
            if path.selected:
                path.quality_score = best_eval.quality_score
                path.status = "selected"
            else:
                path.status = "evaluated"
        final_structured.learning_signals.evaluation_notes.append(f"selected_path:{best_path}")
        await self._query_logger.run("evaluation", best_eval.model_dump())
        if not best_eval.success:
            for policy_item in final_structured.failure_policies:
                if policy_item.failure_type in (best_eval.failure_signals or []):
                    policy_item.applied = True
        state["final_structured_query"] = final_structured
        response = best_response or self._builder.build_search_response(state)
        if final_structured.user_context.predicted_needs:
            response.metadata["predicted_needs"] = final_structured.user_context.predicted_needs
        response.metadata["coordination_trace"] = self._coordination.trace()
        response.metadata["platform_signals"] = final_structured.platform_signals
        budget_limit = (final_structured.constraints.budget or {}).get("amount")
        if budget_limit:
            response.results = [r for r in response.results if float(r.get("price", 0)) <= float(budget_limit)]
            if response.best_option and float(response.best_option.get("price", 0)) > float(budget_limit):
                response.best_option = {}
            if not response.best_option and response.results:
                response.best_option = response.results[0]
            response.total_price = response.best_option.get("price", 0.0) if response.best_option else 0.0
            if not response.results:
                response.metadata["no_results_message"] = "No products found within budget"
        if best_eval.success:
            await self._learning_loop.learn_from_success(final_structured)
        else:
            await self._learning_loop.learn_from_outcome(final_structured, success=False)
        await self._platform_events.ingest(
            event=PlatformEvent(
                event_type=PlatformEventType.user_behavior,
                user_id=final_structured.user_context.user_id or "anonymous",
                payload={
                    "action": "search_execute",
                    "query": final_structured.clean_query.normalized_text,
                    "best_option": response.best_option.get("name") if isinstance(response.best_option, dict) else None,
                    "selected_path": best_path,
                },
            )
        )
        logger.debug(
            "[FINAL_OUTPUT] result_count=%s total_price=%s deals=%s",
            len(response.results),
            response.total_price,
            len(response.deals),
        )
        return response

    async def run_recipe(self, query: str, servings: int = 2) -> FinalResponse:
        """Execute the recipe pipeline."""
        logger.debug("[ENTRY] endpoint=/ai/recipe query=%s type=recipe", query)
        state: Dict[str, Any] = {"raw_query": query}
        state["recipe_result"] = await self._recipe_agent.run(query, servings)
        response = self._builder.build_recipe_response(state)
        logger.debug(
            "[FINAL_OUTPUT] result_count=%s total_price=%s deals=%s",
            len(response.results),
            response.total_price,
            len(response.deals),
        )
        return response

    async def run_cart_optimize(self, items: List[CartItem]) -> FinalResponse:
        """Find the optimal platform split for a list of cart items."""
        logger.debug(
            "[ENTRY] endpoint=/ai/cart-optimize query=%s type=cart_optimize",
            ",".join(item.name for item in items),
        )
        state: Dict[str, Any] = {"cart_items": items}

        # For each item, find globally optimized option across platforms (cost + delivery)
        item_best: Dict[str, Any] = {}
        for item in items:
            normalized_item = await self._normalization_agent.run(item.name)
            products = get_products_for_entity(normalized_item.canonical_name)
            if not products:
                continue
            best = min((p for p in products if p.in_stock), key=self._global_product_objective, default=None)
            if best:
                item_best[item.name] = best

        # Group cheapest items by platform
        platform_groups: Dict[str, CartPlatformGroup] = {}
        total_cost = 0.0
        for item_name, product in item_best.items():
            plat = product.platform
            if plat not in platform_groups:
                platform_groups[plat] = CartPlatformGroup(platform=plat, items=[], subtotal=0.0)
            platform_groups[plat].items.append(product)
            platform_groups[plat].subtotal = round(
                platform_groups[plat].subtotal + product.price, 2
            )
            total_cost += product.price

        # Compare with single-platform cost
        single_platform_costs: Dict[str, float] = {}
        for item in items:
            normalized_item = await self._normalization_agent.run(item.name)
            products = get_products_for_entity(normalized_item.canonical_name)
            for p in products:
                plat = p.platform.value
                single_platform_costs[plat] = single_platform_costs.get(plat, 0) + p.price
        max_single = max(single_platform_costs.values()) if single_platform_costs else total_cost
        savings = round(max_single - total_cost, 2) if max_single > total_cost else 0.0

        result = CartOptimizationResult(
            original_items=items,
            platform_groups=list(platform_groups.values()),
            total_optimized_cost=round(total_cost, 2),
            savings=savings,
        )
        state["cart_result"] = result
        response = self._builder.build_cart_response(state)
        response.metadata["global_optimization"] = {
            "objective": "cost_delivery_availability",
            "delivery_weight": _GLOBAL_OPTIMIZATION_DELIVERY_WEIGHT,
            "stores_considered": list({group.platform.value for group in result.platform_groups}),
        }
        logger.debug(
            "[FINAL_OUTPUT] result_count=%s total_price=%s deals=%s",
            len(response.results),
            response.total_price,
            len(response.deals),
        )
        return response

    @staticmethod
    def _sanitize_candidate_entities(entities: List[str]) -> List[str]:
        return list(dict.fromkeys([e for e in entities if isinstance(e, str) and e.strip()]))[:_MAX_CANDIDATE_ENTITIES]

    def _apply_budget_optimization(self, ranking_result: Any, budget_limit: Any) -> Any:
        if not budget_limit:
            return ranking_result
        hard_budget_ranked = [
            item for item in ranking_result.ranked_list
            if item.product and item.product.price <= float(budget_limit)
        ]
        ranked = []
        source_ranked = hard_budget_ranked
        source_ranked_keys = {(item.product.platform.value, item.product.product_id) for item in source_ranked}
        for item in ranking_result.ranked_list:
            item_key = (item.product.platform.value, item.product.product_id)
            if item_key not in source_ranked_keys:
                continue
            optimization_score = self._constraint_optimizer.score_candidate(
                item.product,
                float(budget_limit),
            )
            if optimization_score > _MIN_OPTIMIZATION_SCORE and (not hard_budget_ranked or item.product.price <= float(budget_limit)):
                ranked.append(item)
        ranking_result.ranked_list = ranked
        ranking_result.best_option = ranked[0] if ranked else None
        return ranking_result

    @staticmethod
    def _global_product_objective(product: Any) -> float:
        normalized_delivery = (
            min(float(product.delivery_time_minutes or _DEFAULT_DELIVERY_MINUTES), _MAX_DELIVERY_MINUTES)
            / _MAX_DELIVERY_MINUTES
        )
        return product.price + (_GLOBAL_OPTIMIZATION_DELIVERY_WEIGHT * normalized_delivery * product.price)


# Module-level singleton
_pipeline: Optional[AgentPipeline] = None


def get_pipeline() -> AgentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = AgentPipeline()
    return _pipeline
