"""Ranking Agent.

Determines the best options from a unified product list.

README
------
Core decision-making layer.
Ranking factors: price (40%), delivery_time (30%), rating (20%), discount (10%).
Input: UnifiedProduct
Output: RankingResult
"""

from typing import Dict, List, Optional

from app.data.models import Platform, PlatformProduct, RankedProduct, RankingResult, UnifiedProduct

# Scoring weights (must sum to 1.0)
_WEIGHT_PRICE = 0.40
_WEIGHT_DELIVERY = 0.30
_WEIGHT_RATING = 0.20
_WEIGHT_DISCOUNT = 0.10
_PRICE_FIRST_THRESHOLD = 0.60


def _score_product(
    product: PlatformProduct,
    all_products: List[PlatformProduct],
    ranking_preferences: Optional[Dict[str, float]] = None,
) -> float:
    """Compute a composite score in [0, 1] (higher = better)."""
    prices = [p.price for p in all_products if p.price > 0]
    delivery_times = [p.delivery_time_minutes for p in all_products if p.delivery_time_minutes is not None]
    ratings = [p.rating for p in all_products if p.rating is not None]
    discounts = [p.discount_percent or 0.0 for p in all_products]

    max_price = max(prices) if prices else 1
    min_price = min(prices) if prices else 0
    max_delivery = max(delivery_times) if delivery_times else 1
    min_delivery = min(delivery_times) if delivery_times else 0
    max_rating = max(ratings) if ratings else 5
    min_rating = min(ratings) if ratings else 0
    max_discount = max(discounts) if discounts else 1

    # Price: lower is better → invert
    price_score = (
        1.0 - (product.price - min_price) / (max_price - min_price)
        if max_price != min_price
        else 1.0
    )

    # Delivery: lower is better → invert
    dt = product.delivery_time_minutes or max_delivery
    delivery_score = (
        1.0 - (dt - min_delivery) / (max_delivery - min_delivery)
        if max_delivery != min_delivery
        else 1.0
    )

    # Rating: higher is better
    r = product.rating or 0.0
    rating_score = (
        (r - min_rating) / (max_rating - min_rating)
        if max_rating != min_rating
        else 1.0
    )

    # Discount: higher is better
    d = product.discount_percent or 0.0
    discount_score = d / max_discount if max_discount > 0 else 0.0

    if ranking_preferences:
        price_weight = float(ranking_preferences.get("price", _WEIGHT_PRICE))
        delivery_weight = float(ranking_preferences.get("delivery", _WEIGHT_DELIVERY))
        rating_weight = float(ranking_preferences.get("rating", _WEIGHT_RATING))
        discount_weight = float(ranking_preferences.get("discount", _WEIGHT_DISCOUNT))
    else:
        price_weight = _WEIGHT_PRICE
        delivery_weight = _WEIGHT_DELIVERY
        rating_weight = _WEIGHT_RATING
        discount_weight = _WEIGHT_DISCOUNT

    return round(
        price_weight * price_score
        + delivery_weight * delivery_score
        + rating_weight * rating_score
        + discount_weight * discount_score,
        4,
    )


class RankingAgent:
    """Ranks products by composite score and returns the best option.

    README: Core decision-making layer.
    """

    async def run(
        self,
        unified_product: UnifiedProduct,
        ranking_preferences: Optional[Dict[str, float]] = None,
    ) -> RankingResult:
        products = unified_product.platforms
        if not products:
            return RankingResult(entity=unified_product.entity)

        scored = [
            (p, _score_product(p, products, ranking_preferences=ranking_preferences))
            for p in products
            if p.in_stock
        ]
        price_first = bool(
            ranking_preferences
            and float(ranking_preferences.get("price", 0.0)) >= _PRICE_FIRST_THRESHOLD
        )
        if price_first:
            scored.sort(
                key=lambda x: (
                    x[0].price,
                    x[0].delivery_time_minutes if x[0].delivery_time_minutes is not None else float("inf"),
                    -(x[0].rating if x[0].rating is not None else 0.0),
                    -(x[0].discount_percent if x[0].discount_percent is not None else 0.0),
                )
            )
        else:
            scored.sort(key=lambda x: x[1], reverse=True)

        ranked_list = [
            RankedProduct(
                platform=p.platform,
                product=p,
                score=score,
                rank=idx + 1,
            )
            for idx, (p, score) in enumerate(scored)
        ]

        return RankingResult(
            entity=unified_product.entity,
            ranked_list=ranked_list,
            best_option=ranked_list[0] if ranked_list else None,
        )
