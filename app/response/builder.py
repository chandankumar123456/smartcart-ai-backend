"""Response Builder.

Combines agent outputs and returns a FinalResponse with the standard structure:
  {query, results, best_option, deals, total_price, metadata}

README
------
Ensures consistent JSON output across all endpoints.
"""

from typing import Any, Dict

from app.data.models import FinalResponse


class ResponseBuilder:
    """Assembles FinalResponse from pipeline state."""

    def build_search_response(self, state: Dict[str, Any]) -> FinalResponse:
        raw_query = state.get("raw_query", "")
        ranking = state.get("ranking_result")
        deal_result = state.get("deal_result")

        results = []
        if ranking:
            for ranked in ranking.ranked_list:
                results.append({
                    "platform": ranked.platform.value,
                    "product_id": ranked.product.product_id,
                    "name": ranked.product.name,
                    "price": ranked.product.price,
                    "original_price": ranked.product.original_price,
                    "discount_percent": ranked.product.discount_percent,
                    "unit": ranked.product.unit,
                    "rating": ranked.product.rating,
                    "delivery_time_minutes": ranked.product.delivery_time_minutes,
                    "in_stock": ranked.product.in_stock,
                    "score": ranked.score,
                    "rank": ranked.rank,
                })

        best_option: Dict[str, Any] = {}
        if ranking and ranking.best_option:
            bo = ranking.best_option
            best_option = {
                "platform": bo.platform.value,
                "product_id": bo.product.product_id,
                "name": bo.product.name,
                "price": bo.product.price,
                "unit": bo.product.unit,
                "delivery_time_minutes": bo.product.delivery_time_minutes,
                "score": bo.score,
            }

        deals = []
        if deal_result:
            for deal in deal_result.deals:
                deals.append({
                    "platform": deal.platform.value,
                    "product_name": deal.product_name,
                    "original_price": deal.original_price,
                    "current_price": deal.current_price,
                    "discount_percent": deal.discount_percent,
                    "deal_type": deal.deal_type,
                    "label": deal.label,
                })

        total_price = best_option.get("price", 0.0)

        return FinalResponse(
            query=raw_query,
            results=results,
            best_option=best_option,
            deals=deals,
            total_price=total_price,
            metadata={
                "intent": state["structured_query"].intent.value if state.get("structured_query") else "",
                "total_results": len(results),
                "total_deals": len(deals),
            },
        )

    def build_recipe_response(self, state: Dict[str, Any]) -> FinalResponse:
        raw_query = state.get("raw_query", "")
        recipe: Any = state.get("recipe_result")

        results = []
        best_option: Dict[str, Any] = {}
        total_price = 0.0

        if recipe:
            total_price = recipe.total_estimated_cost
            for ip in recipe.ingredients:
                item: Dict[str, Any] = {
                    "ingredient": {
                        "name": ip.ingredient.name,
                        "quantity": ip.ingredient.quantity,
                        "unit": ip.ingredient.unit,
                    },
                    "cheapest_option": None,
                    "available_on": [],
                }
                if ip.cheapest_option:
                    item["cheapest_option"] = {
                        "platform": ip.cheapest_option.platform.value,
                        "name": ip.cheapest_option.name,
                        "price": ip.cheapest_option.price,
                        "unit": ip.cheapest_option.unit,
                    }
                item["available_on"] = [p.platform.value for p in ip.matched_products]
                results.append(item)

            best_option = {
                "recipe_name": recipe.recipe_name,
                "servings": recipe.servings,
                "total_estimated_cost": recipe.total_estimated_cost,
                "missing_items": recipe.missing_items,
            }

        return FinalResponse(
            query=raw_query,
            results=results,
            best_option=best_option,
            deals=[],
            total_price=total_price,
            metadata={
                "intent": "recipe",
                "ingredient_count": len(results),
            },
        )

    def build_cart_response(self, state: Dict[str, Any]) -> FinalResponse:
        items = state.get("cart_items", [])
        cart_result = state.get("cart_result")

        results = []
        best_option: Dict[str, Any] = {}
        total_price = 0.0

        if cart_result:
            total_price = cart_result.total_optimized_cost
            for pg in cart_result.platform_groups:
                group: Dict[str, Any] = {
                    "platform": pg.platform.value,
                    "items": [
                        {
                            "name": p.name,
                            "price": p.price,
                            "unit": p.unit,
                        }
                        for p in pg.items
                    ],
                    "subtotal": pg.subtotal,
                }
                results.append(group)

            best_option = {
                "total_optimized_cost": cart_result.total_optimized_cost,
                "savings": cart_result.savings,
                "platform_count": len(cart_result.platform_groups),
            }

        return FinalResponse(
            query=", ".join(i.name for i in items),
            results=results,
            best_option=best_option,
            deals=[],
            total_price=total_price,
            metadata={
                "intent": "cart_optimize",
                "item_count": len(items),
            },
        )
