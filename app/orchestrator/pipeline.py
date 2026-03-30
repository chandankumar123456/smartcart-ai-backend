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

from typing import Any, Dict, List, Optional

from app.agents.deal_detection import DealDetectionAgent
from app.agents.product_matching import ProductMatchingAgent
from app.agents.query_understanding import QueryUnderstandingAgent
from app.agents.ranking import RankingAgent
from app.agents.recipe import RecipeAgent
from app.data.layer import get_products_for_entity
from app.data.models import (
    CartItem,
    CartOptimizationResult,
    CartPlatformGroup,
    FinalResponse,
    QueryIntent,
    RecipeResult,
    StructuredQuery,
)
from app.llm.manager import LLMManager, get_llm_manager
from app.response.builder import ResponseBuilder


class AgentPipeline:
    """Sequential multi-agent pipeline (LangGraph-compatible design).

    Each step receives the accumulated state dict and returns updated state.
    This mirrors LangGraph's StateGraph pattern and can be trivially wrapped
    in a real LangGraph graph if the package is available.
    """

    def __init__(self, llm_manager: Optional[LLMManager] = None) -> None:
        llm = llm_manager or get_llm_manager()
        self._query_agent = QueryUnderstandingAgent(llm)
        self._product_agent = ProductMatchingAgent()
        self._ranking_agent = RankingAgent()
        self._deal_agent = DealDetectionAgent()
        self._recipe_agent = RecipeAgent(llm)
        self._builder = ResponseBuilder()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def run_search(self, query: str) -> FinalResponse:
        """Execute the full search pipeline for a user query."""
        state: Dict[str, Any] = {"raw_query": query}

        # Step 1: Understand query
        state["structured_query"] = await self._query_agent.run(query)

        # Step 2: If recipe intent, delegate to recipe pipeline
        sq: StructuredQuery = state["structured_query"]
        if sq.intent == QueryIntent.recipe:
            return await self.run_recipe(query)

        # Step 3: Match products
        state["unified_product"] = await self._product_agent.run(sq)

        # Step 4: Rank
        state["ranking_result"] = await self._ranking_agent.run(state["unified_product"])

        # Step 5: Detect deals
        state["deal_result"] = await self._deal_agent.run(state["unified_product"])

        return self._builder.build_search_response(state)

    async def run_recipe(self, query: str, servings: int = 2) -> FinalResponse:
        """Execute the recipe pipeline."""
        state: Dict[str, Any] = {"raw_query": query}
        state["recipe_result"] = await self._recipe_agent.run(query, servings)
        return self._builder.build_recipe_response(state)

    async def run_cart_optimize(self, items: List[CartItem]) -> FinalResponse:
        """Find the optimal platform split for a list of cart items."""
        state: Dict[str, Any] = {"cart_items": items}

        # For each item, find cheapest option across platforms
        item_cheapest: Dict[str, Any] = {}
        for item in items:
            products = get_products_for_entity(item.name)
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
            products = get_products_for_entity(item.name)
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
        return self._builder.build_cart_response(state)


# Module-level singleton
_pipeline: Optional[AgentPipeline] = None


def get_pipeline() -> AgentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = AgentPipeline()
    return _pipeline
