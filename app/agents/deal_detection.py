"""Deal Detection Agent.

Identifies discounts, price drops, and trending deals from a product list.

README
------
Adds savings intelligence beyond simple price comparison.
Input: UnifiedProduct
Output: DealResult
"""

from typing import Any, Dict, Mapping

from app.agents.base_execution import BaseExecutionAgent
from app.data.models import Deal, DealResult, Platform, PlatformProduct, UnifiedProduct

_DISCOUNT_THRESHOLD = 5.0   # % — minimum discount to flag as a deal
_TRENDING_THRESHOLD = 10.0  # % — discount above which a deal is "trending"


def _build_deal(product: PlatformProduct, deal_type: str) -> Deal:
    original = product.original_price or product.price
    discount = product.discount_percent or 0.0
    label = f"Save {discount:.0f}% on {product.name}"
    return Deal(
        platform=product.platform,
        product_name=product.name,
        original_price=original,
        current_price=product.price,
        discount_percent=discount,
        deal_type=deal_type,
        label=label,
    )


class DealDetectionAgent(BaseExecutionAgent):
    """Scans a unified product set for deals above configured thresholds.

    README: Adds savings intelligence beyond comparison.
    """

    async def run(self, unified_product: UnifiedProduct) -> DealResult:
        deals: list[Deal] = []
        trending: list[Deal] = []

        for product in unified_product.platforms:
            discount = product.discount_percent or 0.0
            if discount >= _TRENDING_THRESHOLD:
                deal = _build_deal(product, "trending")
                trending.append(deal)
                deals.append(deal)
            elif discount >= _DISCOUNT_THRESHOLD:
                deal = _build_deal(product, "discount")
                deals.append(deal)

        # Sort by discount descending
        deals.sort(key=lambda d: d.discount_percent, reverse=True)
        trending.sort(key=lambda d: d.discount_percent, reverse=True)

        return DealResult(deals=deals, trending_deals=trending)

    async def act(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        deal_result = await self.run(state["unified_product"])
        return {
            "current_step": "deal_detection_node",
            "deal_result": deal_result,
            "deals": deal_result,
            "last_observation": {
                "deal_count": len(deal_result.deals),
                "trending_count": len(deal_result.trending_deals),
            },
        }
