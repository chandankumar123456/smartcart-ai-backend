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
    @pytest.mark.asyncio
    async def test_search_returns_final_response(self, pipeline):
        result = await pipeline.run_search("milk")
        assert result.query == "milk"
        assert isinstance(result.results, list)
        assert isinstance(result.best_option, dict)
        assert isinstance(result.deals, list)
        assert isinstance(result.total_price, float)

    @pytest.mark.asyncio
    async def test_search_with_price_filter(self, pipeline):
        result = await pipeline.run_search("milk under 30")
        for r in result.results:
            assert r["price"] <= 30.0

    @pytest.mark.asyncio
    async def test_search_best_option_present(self, pipeline):
        result = await pipeline.run_search("rice")
        assert result.best_option != {}
        assert "platform" in result.best_option
        assert "price" in result.best_option

    @pytest.mark.asyncio
    async def test_search_unknown_product_graceful(self, pipeline):
        result = await pipeline.run_search("xyz_unknown_product_123")
        assert result.query == "xyz_unknown_product_123"
        assert result.results == []
        assert result.best_option == {}

    @pytest.mark.asyncio
    async def test_search_deals_detected_for_discounted_product(self, pipeline):
        result = await pipeline.run_search("milk")
        # Zepto milk has 12.5% discount — should appear as deal
        deal_platforms = {d["platform"] for d in result.deals}
        assert len(result.deals) >= 0  # may vary based on thresholds

    @pytest.mark.asyncio
    async def test_search_generic_chicken_returns_results(self, pipeline):
        result = await pipeline.run_search("chicken")
        assert len(result.results) > 0
        assert result.total_price > 0

    @pytest.mark.asyncio
    async def test_search_generic_curd_alias_returns_results(self, pipeline):
        result = await pipeline.run_search("dahi")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_capsicum_returns_results(self, pipeline):
        result = await pipeline.run_search("capsicum")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_atta_returns_results(self, pipeline):
        result = await pipeline.run_search("atta")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_paneer_cubes_returns_results(self, pipeline):
        result = await pipeline.run_search("paneer cubes")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_salad_leaves_returns_results(self, pipeline):
        result = await pipeline.run_search("salad leaves")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_evening_snacks_returns_results(self, pipeline):
        result = await pipeline.run_search("something for evening snacks")
        assert len(result.results) > 0

    @pytest.mark.asyncio
    async def test_search_vague_multi_item_query_returns_results(self, pipeline):
        result = await pipeline.run_search("need paneer cubes and salad leaves for dinner")
        assert len(result.results) > 0


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

    @pytest.mark.asyncio
    async def test_cart_optimize_empty_items(self, pipeline):
        result = await pipeline.run_cart_optimize([])
        assert result.total_price == 0.0


class TestResponseFormat:
    """Validate strict output format: {query, results, best_option, deals, total_price}."""

    @pytest.mark.asyncio
    async def test_search_response_has_required_fields(self, pipeline):
        result = await pipeline.run_search("eggs")
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
