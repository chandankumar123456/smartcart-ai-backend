"""Intent Detection Agent."""

from __future__ import annotations

from app.data.models import CleanQuery, IntentResult, QueryIntent

_RECIPE_KEYWORDS = {"recipe", "cook", "prepare", "make", "dish", "biryani", "curry", "pasta", "soup", "salad"}
_CART_KEYWORDS = {"optimize", "cart", "basket", "total", "split"}
_EXPLORATORY_KEYWORDS = {"something", "anything", "some", "options", "ideas"}
_NON_GROCERY_KEYWORDS = {
    "laptop", "phone", "mobile", "charger", "headphones", "movie", "flight", "hotel",
    "stocks", "crypto", "insurance", "car", "bike", "shoes", "shirt",
}
_GROCERY_CONTEXT = {"grocery", "groceries", "food", "ingredient", "ingredients", "milk", "rice", "bread", "eggs"}
_UNSUPPORTED_CONFIDENCE = 0.95
_RECIPE_CONFIDENCE = 0.88
_CART_CONFIDENCE = 0.86
_EXPLORATORY_CONFIDENCE = 0.74
_DEFAULT_SEARCH_CONFIDENCE = 0.8


class IntentDetectionAgent:
    async def run(self, clean_query: CleanQuery) -> IntentResult:
        q = clean_query.normalized_text
        words = set(clean_query.tokens)
        secondary_intents = []
        has_non_grocery = bool(words.intersection(_NON_GROCERY_KEYWORDS))
        has_grocery = bool(words.intersection(_GROCERY_CONTEXT))
        if has_non_grocery and not has_grocery:
            return IntentResult(
                intent=QueryIntent.unsupported,
                confidence=_UNSUPPORTED_CONFIDENCE,
                notes="non-grocery query",
                secondary_intents=[],
            )
        has_recipe = any(k in q for k in _RECIPE_KEYWORDS)
        has_cart = any(k in q for k in _CART_KEYWORDS)
        if has_recipe and has_cart:
            secondary_intents = [QueryIntent.cart_optimization]
            return IntentResult(
                intent=QueryIntent.recipe,
                confidence=max(_RECIPE_CONFIDENCE, _CART_CONFIDENCE),
                notes="multi-intent recipe + cart optimization",
                secondary_intents=secondary_intents,
            )
        if any(k in q for k in _RECIPE_KEYWORDS):
            return IntentResult(
                intent=QueryIntent.recipe,
                confidence=_RECIPE_CONFIDENCE,
                notes="recipe intent",
                secondary_intents=[],
            )
        if any(k in q for k in _CART_KEYWORDS):
            return IntentResult(
                intent=QueryIntent.cart_optimization,
                confidence=_CART_CONFIDENCE,
                notes="cart optimization intent",
                secondary_intents=[],
            )
        if any(k in words for k in _EXPLORATORY_KEYWORDS):
            return IntentResult(
                intent=QueryIntent.exploratory,
                confidence=_EXPLORATORY_CONFIDENCE,
                notes="exploratory intent",
                secondary_intents=[],
            )
        return IntentResult(
            intent=QueryIntent.product_search,
            confidence=_DEFAULT_SEARCH_CONFIDENCE,
            notes="default grocery search intent",
            secondary_intents=[],
        )
