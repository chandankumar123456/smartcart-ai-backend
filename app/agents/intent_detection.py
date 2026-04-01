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


class IntentDetectionAgent:
    async def run(self, clean_query: CleanQuery) -> IntentResult:
        q = clean_query.normalized_text
        words = set(clean_query.tokens)
        has_non_grocery = bool(words.intersection(_NON_GROCERY_KEYWORDS))
        has_grocery = bool(words.intersection(_GROCERY_CONTEXT))
        if has_non_grocery and not has_grocery:
            return IntentResult(intent=QueryIntent.unsupported, confidence=0.95, notes="non-grocery query")
        if any(k in q for k in _RECIPE_KEYWORDS):
            return IntentResult(intent=QueryIntent.recipe, confidence=0.88, notes="recipe intent")
        if any(k in q for k in _CART_KEYWORDS):
            return IntentResult(intent=QueryIntent.cart_optimization, confidence=0.86, notes="cart optimization intent")
        if any(k in words for k in _EXPLORATORY_KEYWORDS):
            return IntentResult(intent=QueryIntent.exploratory, confidence=0.74, notes="exploratory intent")
        return IntentResult(intent=QueryIntent.product_search, confidence=0.8, notes="default grocery search intent")
