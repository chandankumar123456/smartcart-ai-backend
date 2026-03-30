"""Tests for AI agents."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.deal_detection import DealDetectionAgent
from app.agents.product_matching import ProductMatchingAgent
from app.agents.query_understanding import QueryUnderstandingAgent, _rule_based_parse
from app.agents.ranking import RankingAgent
from app.agents.recipe import RecipeAgent
from app.data.models import (
    Platform,
    PlatformProduct,
    QueryFilters,
    QueryIntent,
    StructuredQuery,
    UnifiedProduct,
)


# ---------------------------------------------------------------------------
# Query Understanding Agent
# ---------------------------------------------------------------------------


class TestQueryUnderstandingAgentRuleBased:
    def test_simple_product(self):
        result = _rule_based_parse("cheap milk under 60")
        assert result["product"] == "milk"
        assert result["filters"]["max_price"] == 60.0
        assert result["intent"] == QueryIntent.product_search.value

    def test_recipe_intent(self):
        result = _rule_based_parse("recipe for tomato pasta")
        assert result["intent"] == QueryIntent.recipe.value

    def test_deal_intent(self):
        result = _rule_based_parse("best deals on bread today")
        assert result["intent"] == QueryIntent.deal_search.value

    def test_cart_intent(self):
        result = _rule_based_parse("optimize my cart total")
        assert result["intent"] == QueryIntent.cart_optimize.value

    def test_price_extraction_with_rupee_symbol(self):
        result = _rule_based_parse("milk under ₹50")
        assert result["filters"]["max_price"] == 50.0

    def test_price_extraction_upto(self):
        result = _rule_based_parse("rice upto 130")
        assert result["filters"]["max_price"] == 130.0

    def test_empty_product_fallback(self):
        result = _rule_based_parse("tomato")
        assert result["product"] == "tomato"

    def test_generic_ingredient_terms_extracted(self):
        result = _rule_based_parse("need chicken and curd")
        assert result["product"] in {"chicken", "curd"}

    def test_ghee_known_product(self):
        result = _rule_based_parse("buy ghee")
        assert result["product"] == "ghee"


class TestQueryUnderstandingAgentLLM:
    @pytest.mark.asyncio
    async def test_run_with_llm_success(self):
        mock_llm = AsyncMock()
        mock_llm.call.return_value = {
            "product": "milk",
            "filters": {"max_price": 60, "min_price": None, "category": "dairy", "quantity": None, "brand": None},
            "intent": "product_search",
        }
        agent = QueryUnderstandingAgent(mock_llm)
        result = await agent.run("cheap milk under 60")
        assert result.product == "milk"
        assert result.filters.max_price == 60.0
        assert result.intent == QueryIntent.product_search

    @pytest.mark.asyncio
    async def test_run_falls_back_on_llm_error(self):
        mock_llm = AsyncMock()
        mock_llm.call.side_effect = Exception("LLM unavailable")
        agent = QueryUnderstandingAgent(mock_llm)
        result = await agent.run("cheap milk under 60")
        assert result.product == "milk"
        assert result.intent == QueryIntent.product_search

    @pytest.mark.asyncio
    async def test_run_raises_on_empty_query(self):
        mock_llm = AsyncMock()
        agent = QueryUnderstandingAgent(mock_llm)
        with pytest.raises(Exception, match="Empty query"):
            await agent.run("")


# ---------------------------------------------------------------------------
# Product Matching Agent
# ---------------------------------------------------------------------------


class TestProductMatchingAgent:
    @pytest.mark.asyncio
    async def test_match_known_product(self):
        agent = ProductMatchingAgent()
        sq = StructuredQuery(product="milk", filters=QueryFilters(), intent=QueryIntent.product_search, raw_query="milk")
        result = await agent.run(sq)
        assert result.entity == "milk"
        assert len(result.platforms) > 0

    @pytest.mark.asyncio
    async def test_price_filter_applied(self):
        agent = ProductMatchingAgent()
        sq = StructuredQuery(
            product="milk",
            filters=QueryFilters(max_price=28.0),
            intent=QueryIntent.product_search,
            raw_query="milk under 28",
        )
        result = await agent.run(sq)
        for p in result.platforms:
            assert p.price <= 28.0

    @pytest.mark.asyncio
    async def test_unknown_product_returns_empty(self):
        agent = ProductMatchingAgent()
        sq = StructuredQuery(product="xyz_nonexistent", filters=QueryFilters(), intent=QueryIntent.product_search, raw_query="xyz")
        result = await agent.run(sq)
        assert result.platforms == []

    @pytest.mark.asyncio
    async def test_match_generic_chicken_term(self):
        agent = ProductMatchingAgent()
        sq = StructuredQuery(product="chicken", filters=QueryFilters(), intent=QueryIntent.product_search, raw_query="chicken")
        result = await agent.run(sq)
        assert len(result.platforms) > 0

    @pytest.mark.asyncio
    async def test_match_synonym_dahi_to_curd(self):
        agent = ProductMatchingAgent()
        sq = StructuredQuery(product="dahi", filters=QueryFilters(), intent=QueryIntent.product_search, raw_query="dahi")
        result = await agent.run(sq)
        assert len(result.platforms) > 0
        assert all(p.normalized_name == "curd" for p in result.platforms)

    @pytest.mark.asyncio
    async def test_top_k_fallback_when_filters_remove_all(self):
        agent = ProductMatchingAgent()
        sq = StructuredQuery(
            product="ghee",
            filters=QueryFilters(max_price=10.0),
            intent=QueryIntent.product_search,
            raw_query="cheap ghee under 10",
        )
        result = await agent.run(sq)
        assert len(result.platforms) == 3


# ---------------------------------------------------------------------------
# Ranking Agent
# ---------------------------------------------------------------------------


class TestRankingAgent:
    def _make_product(self, platform: Platform, price: float, delivery: int, rating: float, discount: float = 0.0) -> PlatformProduct:
        return PlatformProduct(
            platform=platform,
            product_id=f"{platform}-test",
            name=f"{platform} product",
            normalized_name="test",
            price=price,
            delivery_time_minutes=delivery,
            rating=rating,
            discount_percent=discount,
        )

    @pytest.mark.asyncio
    async def test_best_option_is_highest_scored(self):
        agent = RankingAgent()
        products = [
            self._make_product(Platform.blinkit, 30.0, 12, 4.5, 10.0),
            self._make_product(Platform.zepto, 50.0, 40, 3.0, 0.0),
        ]
        unified = UnifiedProduct(entity="milk", platforms=products)
        result = await agent.run(unified)
        assert result.best_option is not None
        assert result.best_option.platform == Platform.blinkit
        assert len(result.ranked_list) == 2

    @pytest.mark.asyncio
    async def test_empty_products_returns_empty_ranking(self):
        agent = RankingAgent()
        unified = UnifiedProduct(entity="milk", platforms=[])
        result = await agent.run(unified)
        assert result.ranked_list == []
        assert result.best_option is None

    @pytest.mark.asyncio
    async def test_ranks_are_sequential(self):
        agent = RankingAgent()
        products = [
            self._make_product(Platform.blinkit, 30.0, 12, 4.5),
            self._make_product(Platform.zepto, 32.0, 10, 4.3),
            self._make_product(Platform.bigbasket, 29.0, 30, 4.6),
        ]
        unified = UnifiedProduct(entity="milk", platforms=products)
        result = await agent.run(unified)
        ranks = [r.rank for r in result.ranked_list]
        assert ranks == [1, 2, 3]


# ---------------------------------------------------------------------------
# Deal Detection Agent
# ---------------------------------------------------------------------------


class TestDealDetectionAgent:
    def _make_discounted_product(self, platform: Platform, price: float, original: float) -> PlatformProduct:
        discount = round((original - price) / original * 100, 1)
        return PlatformProduct(
            platform=platform,
            product_id=f"{platform}-deal",
            name=f"{platform} deal product",
            normalized_name="deal",
            price=price,
            original_price=original,
            discount_percent=discount,
        )

    @pytest.mark.asyncio
    async def test_detects_deals_above_threshold(self):
        agent = DealDetectionAgent()
        products = [
            self._make_discounted_product(Platform.zepto, 28.0, 32.0),   # 12.5%
            self._make_discounted_product(Platform.blinkit, 30.0, 30.0),  # 0%
        ]
        unified = UnifiedProduct(entity="milk", platforms=products)
        result = await agent.run(unified)
        assert len(result.deals) == 1
        assert result.deals[0].platform == Platform.zepto

    @pytest.mark.asyncio
    async def test_trending_deals_above_threshold(self):
        agent = DealDetectionAgent()
        products = [
            self._make_discounted_product(Platform.zepto, 28.0, 32.0),   # 12.5% → trending
        ]
        unified = UnifiedProduct(entity="milk", platforms=products)
        result = await agent.run(unified)
        assert len(result.trending_deals) == 1

    @pytest.mark.asyncio
    async def test_no_deals_returns_empty(self):
        agent = DealDetectionAgent()
        products = [
            PlatformProduct(
                platform=Platform.blinkit,
                product_id="bl-001",
                name="Product",
                normalized_name="product",
                price=30.0,
                discount_percent=0.0,
            )
        ]
        unified = UnifiedProduct(entity="test", platforms=products)
        result = await agent.run(unified)
        assert result.deals == []


# ---------------------------------------------------------------------------
# Recipe Agent
# ---------------------------------------------------------------------------


class TestRecipeAgent:
    @pytest.mark.asyncio
    async def test_recipe_returns_ingredients(self):
        mock_llm = AsyncMock()
        mock_llm.call.side_effect = Exception("LLM unavailable")  # force static fallback
        agent = RecipeAgent(mock_llm)
        result = await agent.run("tomato pasta", servings=2)
        assert result.recipe_name != ""
        assert len(result.ingredients) > 0

    @pytest.mark.asyncio
    async def test_recipe_maps_known_ingredients(self):
        mock_llm = AsyncMock()
        mock_llm.call.return_value = {
            "recipe_name": "Milk Tea",
            "servings": 2,
            "ingredients": [
                {"name": "milk", "quantity": "200", "unit": "ml"},
            ],
        }
        agent = RecipeAgent(mock_llm)
        result = await agent.run("milk tea")
        assert len(result.ingredients) == 1
        ip = result.ingredients[0]
        assert ip.ingredient.name == "milk"
        assert len(ip.matched_products) > 0
        assert ip.cheapest_option is not None

    @pytest.mark.asyncio
    async def test_total_cost_computed(self):
        mock_llm = AsyncMock()
        mock_llm.call.return_value = {
            "recipe_name": "Rice Bowl",
            "servings": 2,
            "ingredients": [
                {"name": "rice", "quantity": "1", "unit": "cup"},
            ],
        }
        agent = RecipeAgent(mock_llm)
        result = await agent.run("rice bowl")
        assert result.total_estimated_cost > 0
