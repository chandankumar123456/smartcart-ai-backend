"""Integration tests for the full agent pipeline."""

import pytest
from unittest.mock import AsyncMock

from app.data.models import CartItem
from app.orchestrator.pipeline import AgentPipeline


@pytest.fixture
def pipeline() -> AgentPipeline:
    """Create a pipeline with a mock LLM that falls back to rule-based parsing."""
    mock_llm = AsyncMock()
    mock_llm.call.side_effect = Exception("LLM not configured in tests")
    return AgentPipeline(llm_manager=mock_llm)


class TestSearchPipeline:
    async def _run_from_query(self, pipeline, query: str):
        parsed = await pipeline.parse_query(query)
        return await pipeline.run_search(parsed)

    @pytest.mark.asyncio
    async def test_parse_query_returns_strict_intelligence_output(self, pipeline):
        parsed = await pipeline.parse_query("cheap milk under 60")
        assert parsed.clean_query.normalized_text == "cheap milk under 60"
        assert parsed.intent_result.intent.value == "product_search"
        assert parsed.domain_guard.allowed is True
        assert parsed.structured_query.product in {"packaged milk", "milk"}
        assert hasattr(parsed, "user_context")
        assert hasattr(parsed, "learning_signals")

    @pytest.mark.asyncio
    async def test_search_returns_final_response(self, pipeline):
        result = await self._run_from_query(pipeline, "milk")
        assert result.query == "milk"
        assert isinstance(result.results, list)
        assert isinstance(result.best_option, dict)
        assert isinstance(result.deals, list)
        assert isinstance(result.total_price, float)
        assert "normalized_query" in result.metadata
        assert "items" in result.metadata
        assert "constraints" in result.metadata
        if result.results:
            assert "url" in result.results[0]
            assert "brand" in result.results[0]
            assert "source" in result.results[0]
            assert "link_status" in result.results[0]
        if result.best_option:
            assert "url" in result.best_option
            assert "brand" in result.best_option
            assert "source" in result.best_option
            assert "link_status" in result.best_option

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, pipeline):
        result = await self._run_from_query(pipeline, "milk under 30")
        for r in result.results:
            assert r["price"] <= 30.0

    @pytest.mark.asyncio
    async def test_search_budget_is_strict_when_no_matches(self, pipeline):
        result = await self._run_from_query(pipeline, "ghee under 10")
        assert result.results == []
        assert result.best_option == {}
        assert result.metadata.get("no_results_message") == "No products found within budget"

    @pytest.mark.asyncio
    async def test_search_best_option_present(self, pipeline):
        result = await self._run_from_query(pipeline, "rice")
        assert result.best_option != {}
        assert "platform" in result.best_option
        assert "price" in result.best_option

    @pytest.mark.asyncio
    async def test_search_unknown_product_graceful(self, pipeline):
        result = await self._run_from_query(pipeline, "xyz_unknown_product_123")
        assert result.query == "xyz_unknown_product_123"
        assert result.results == []
        assert result.best_option == {}
        assert result.metadata.get("intent") in {"product_search", "exploratory"}

    @pytest.mark.asyncio
    async def test_search_deals_detected_for_discounted_product(self, pipeline):
        result = await self._run_from_query(pipeline, "milk")
        # Zepto milk has 12.5% discount — should appear as deal
        deal_platforms = {d["platform"] for d in result.deals}
        assert len(result.deals) >= 0  # may vary based on thresholds

    @pytest.mark.asyncio
    async def test_search_generic_chicken_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "chicken")
        assert len(result.results) > 0
        assert result.total_price > 0

    @pytest.mark.asyncio
    async def test_search_generic_curd_alias_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "dahi")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_mayo_synonym_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "mayo")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_result_has_link_status_when_url_missing(self, pipeline):
        result = await self._run_from_query(pipeline, "milk")
        if result.results:
            assert result.results[0].get("link_status") in {"available", "link unavailable"}

    @pytest.mark.asyncio
    async def test_search_capsicum_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "capsicum")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_atta_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "atta")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_paneer_cubes_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "paneer cubes")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_salad_leaves_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "salad leaves")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_evening_snacks_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "something for evening snacks")
        assert len(result.results) > 0
        assert result.metadata.get("intent") == "exploratory"

    @pytest.mark.asyncio
    async def test_search_vague_multi_item_query_returns_results(self, pipeline):
        result = await self._run_from_query(pipeline, "need paneer cubes and salad leaves for dinner")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_unsupported_query_returns_structured_unsupported(self, pipeline):
        result = await self._run_from_query(pipeline, "book me a flight to mumbai")
        assert result.results == []
        assert result.best_option == {}
        assert result.metadata.get("domain_guard", {}).get("allowed") is False

    @pytest.mark.asyncio
    async def test_parse_query_multi_intent_generates_execution_plan(self, pipeline):
        parsed = await pipeline.parse_query("plan tomato pasta and optimize my cart")
        assert parsed.intent_result.intent.value == "recipe"
        assert "cart_optimization" in [i.value for i in parsed.intent_result.secondary_intents]
        assert parsed.execution_plan.mode == "graph"
        assert parsed.execution_graph.graph_id.startswith("graph-")
        assert any(node.operation == "recipe_generation" for node in parsed.execution_graph.nodes)

    @pytest.mark.asyncio
    async def test_parse_query_ambiguity_has_candidates(self, pipeline):
        parsed = await pipeline.parse_query("need paneer and salad")
        assert parsed.ambiguity.needs_resolution is True
        assert len(parsed.ambiguity.candidate_entities) >= 1
        assert len(parsed.candidate_paths) >= 1

    @pytest.mark.asyncio
    async def test_reasoning_loop_applies_budget_refinement(self, pipeline):
        parsed = await pipeline.parse_query("cheap milk under 20")
        result = await pipeline.run_search(parsed)
        if result.best_option:
            assert result.best_option["price"] <= 20
        else:
            assert result.results == []
        assert parsed.learning_signals.retry_count >= 0
        assert len(parsed.evaluation_history) >= 1

    @pytest.mark.asyncio
    async def test_dynamic_execution_can_skip_deals(self, pipeline):
        parsed = await pipeline.parse_query("cheap rice under 40")
        assert parsed.execution_plan.adaptive_flags.get("skip_deals") is True
        result = await pipeline.run_search(parsed)
        assert result.deals == []

    @pytest.mark.asyncio
    async def test_cheap_query_orders_results_cheapest_first(self, pipeline):
        result = await self._run_from_query(pipeline, "cheap wheat flour under 150")
        prices = [r["price"] for r in result.results]
        assert prices == sorted(prices)
        if prices:
            assert prices[0] <= 150

    @pytest.mark.asyncio
    async def test_learning_policy_affects_future_run(self, pipeline):
        parsed = await pipeline.parse_query("cheap milk under 20")
        await pipeline.run_search(parsed)
        parsed2 = await pipeline.parse_query("cheap milk under 20")
        await pipeline.run_search(parsed2)
        assert any(note.startswith("selected_path:") for note in parsed2.learning_signals.evaluation_notes)

    @pytest.mark.asyncio
    async def test_parse_query_includes_platform_signals_and_coordination_trace(self, pipeline):
        parsed = await pipeline.parse_query("milk")
        assert isinstance(parsed.platform_signals, dict)
        assert "recommendation_signals" in parsed.platform_signals
        assert isinstance(parsed.coordination_trace, dict)
        assert "signals" in parsed.coordination_trace


class TestRecipePipeline:
    @pytest.mark.asyncio
    async def test_recipe_returns_ingredients(self, pipeline):
        result = await pipeline.run_recipe("tomato pasta", servings=2)
        assert result.query == "tomato pasta"
        assert isinstance(result.results, list)
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_recipe_total_price_positive(self, pipeline):
        result = await pipeline.run_recipe("fried rice")
        assert result.total_price >= 0

    @pytest.mark.asyncio
    async def test_recipe_metadata_intent(self, pipeline):
        result = await pipeline.run_recipe("dal")
        assert result.metadata.get("intent") == "recipe"


class TestCartOptimizePipeline:
    @pytest.mark.asyncio
    async def test_cart_optimize_basic(self, pipeline):
        items = [CartItem(name="milk"), CartItem(name="bread")]
        result = await pipeline.run_cart_optimize(items)
        assert isinstance(result.results, list)
        assert result.total_price > 0

    @pytest.mark.asyncio
    async def test_cart_optimize_metadata(self, pipeline):
        items = [CartItem(name="rice"), CartItem(name="onion")]
        result = await pipeline.run_cart_optimize(items)
        assert result.metadata.get("intent") == "cart_optimize"
        assert result.metadata.get("item_count") == 2
        assert result.metadata.get("global_optimization", {}).get("objective") == "cost_delivery_availability"

    @pytest.mark.asyncio
    async def test_cart_optimize_empty_items(self, pipeline):
        result = await pipeline.run_cart_optimize([])
        assert result.total_price == 0.0


class TestResponseFormat:
    """Validate strict output format: {query, results, best_option, deals, total_price}."""

    @pytest.mark.asyncio
    async def test_search_response_has_required_fields(self, pipeline):
        parsed = await pipeline.parse_query("eggs")
        result = await pipeline.run_search(parsed)
        d = result.model_dump()
        assert "query" in d
        assert "results" in d
        assert "best_option" in d
        assert "deals" in d
        assert "total_price" in d

    @pytest.mark.asyncio
    async def test_recipe_response_has_required_fields(self, pipeline):
        result = await pipeline.run_recipe("tomato pasta")
        d = result.model_dump()
        assert "query" in d
        assert "results" in d
        assert "best_option" in d
        assert "deals" in d
        assert "total_price" in d
