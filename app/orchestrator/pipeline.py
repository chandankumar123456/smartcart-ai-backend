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
    FinalStructuredQuery,
    FinalResponse,
    NormalizedItem,
    QueryFilters,
    QueryMetadata,
    QueryIntent,
    LearningSignals,
    EvaluationResult,
    QueryConstraints,
    RecipeResult,
    StructuredItem,
    StructuredQuery,
)
from app.learning.feedback import LearningLoop
from app.llm.manager import LLMManager, get_llm_manager
from app.response.builder import ResponseBuilder

logger = logging.getLogger(__name__)
_MAX_REASONING_RETRY_ATTEMPTS = 1


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
        execution_plan = await self._execution_planner_agent.run(intent_result)
        await self._query_logger.run("execution_planning", execution_plan.model_dump())
        user_context = await self._user_context_agent.run(clean_query)
        await self._query_logger.run("user_context", user_context.model_dump())
        learning_signals = LearningSignals(
            normalization_reinforced=[e.canonical_name for e in normalized_entities.entities if e.canonical_name],
            failed_matches=list(normalized_entities.unresolved_entities),
            ranking_adjustments=dict(constraints.ranking_preference_weights),
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
            user_context=user_context,
            learning_signals=learning_signals,
            structured_query=structured_query,
        )
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
        if final_structured.execution_plan.mode in {"recipe_only", "recipe_then_cart_optimization"}:
            response = await self.run_recipe(final_structured.clean_query.text)
            if final_structured.execution_plan.mode == "recipe_then_cart_optimization":
                response.metadata["secondary_intents"] = [i.value for i in final_structured.intent_result.secondary_intents]
                response.metadata["execution_plan"] = final_structured.execution_plan.model_dump()
            return response

        if final_structured.normalized_entities.entities:
            primary_normalized = final_structured.normalized_entities.entities[0]
            state["normalized_item"] = NormalizedItem(
                canonical_name=primary_normalized.canonical_name,
                possible_variants=primary_normalized.possible_variants,
                category=primary_normalized.category,
                attributes=[],
            )
        else:
            normalized_term = sq.product or final_structured.clean_query.text
            state["normalized_item"] = await self._normalization_agent.run(normalized_term)
        state["unified_product"] = await self._product_agent.run(sq, state["normalized_item"])
        state["ranking_result"] = await self._ranking_agent.run(
            state["unified_product"],
            ranking_preferences=final_structured.constraints.ranking_preference_weights,
        )
        logger.debug(
            "[RANKING] items_processed=%s",
            len(state["ranking_result"].ranked_list),
        )

        state["deal_result"] = await self._deal_agent.run(state["unified_product"])
        logger.debug("[DEALS] deals_count=%s", len(state["deal_result"].deals))

        response = self._builder.build_search_response(state)
        evaluation: EvaluationResult = await self._evaluation_agent.run(final_structured, response)
        retries = 0
        ambiguity_normalized_cache: Dict[str, NormalizedItem] = {}
        while evaluation.should_retry and retries < _MAX_REASONING_RETRY_ATTEMPTS:
            retries += 1
            final_structured.learning_signals.retry_count = retries
            final_structured.learning_signals.evaluation_notes.extend(evaluation.correction_suggestions)
            if "constraint_violation" in evaluation.failure_signals and final_structured.constraints.budget:
                budget_amount = float(final_structured.constraints.budget.get("amount", 0))
                if budget_amount > 0:
                    filtered = [
                        item for item in state["ranking_result"].ranked_list
                        if item.product and item.product.price is not None and item.product.price <= budget_amount
                    ]
                    state["ranking_result"].ranked_list = filtered
                    state["ranking_result"].best_option = filtered[0] if filtered else None
            if "ambiguity_failure" in evaluation.failure_signals and final_structured.ambiguity.candidate_entities:
                fallback_entity = final_structured.ambiguity.candidate_entities[0]
                if fallback_entity not in ambiguity_normalized_cache:
                    ambiguity_normalized_cache[fallback_entity] = await self._normalization_agent.run(fallback_entity)
                state["normalized_item"] = ambiguity_normalized_cache[fallback_entity]
                state["unified_product"] = await self._product_agent.run(sq, state["normalized_item"])
                state["ranking_result"] = await self._ranking_agent.run(
                    state["unified_product"],
                    ranking_preferences=final_structured.constraints.ranking_preference_weights,
                )
                state["deal_result"] = await self._deal_agent.run(state["unified_product"])
            response = self._builder.build_search_response(state)
            evaluation = await self._evaluation_agent.run(final_structured, response)
        await self._query_logger.run("evaluation", evaluation.model_dump())
        state["final_structured_query"] = final_structured
        response = self._builder.build_search_response(state)
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

        # For each item, find cheapest option across platforms
        item_cheapest: Dict[str, Any] = {}
        for item in items:
            normalized_item = await self._normalization_agent.run(item.name)
            products = get_products_for_entity(normalized_item.canonical_name)
            if not products:
                continue
            cheapest = min(
                (p for p in products if p.in_stock),
                key=lambda p: p.price,
                default=None,
            )
            if cheapest:
                item_cheapest[item.name] = cheapest

        # Group cheapest items by platform
        platform_groups: Dict[str, CartPlatformGroup] = {}
        total_cost = 0.0
        for item_name, product in item_cheapest.items():
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
        logger.debug(
            "[FINAL_OUTPUT] result_count=%s total_price=%s deals=%s",
            len(response.results),
            response.total_price,
            len(response.deals),
        )
        return response


# Module-level singleton
_pipeline: Optional[AgentPipeline] = None


def get_pipeline() -> AgentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = AgentPipeline()
    return _pipeline
