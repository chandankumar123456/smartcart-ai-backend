"""Entity Extraction Agent."""

from __future__ import annotations

from typing import List, Tuple

from app.data.models import CleanQuery, IntentResult, QueryIntent, RawEntities, RawEntity

_KNOWN_PRODUCTS = {
    "milk", "bread", "eggs", "rice", "tomato", "onion", "oil", "butter",
    "pasta", "sugar", "atta", "flour", "salt", "tea", "coffee", "biscuits",
    "chips", "noodles", "cheese", "yogurt", "curd", "chicken", "ghee", "paneer",
    "snacks", "salad", "ginger", "lentils", "cumin seeds", "red chili powder",
    "wheat flour",
}
_STOPWORDS = {"find", "show", "get", "buy", "need", "want", "for", "me", "the", "a", "an", "under", "above"}


def _extract_primary(q: str, intent: QueryIntent) -> Tuple[str, List[str]]:
    if intent == QueryIntent.unsupported:
        return "", []
    if intent == QueryIntent.exploratory:
        return "snacks", ["query_is_exploratory"]
    for product in _KNOWN_PRODUCTS:
        if product in q:
            return product, []
    tokens = [t for t in q.split() if t not in _STOPWORDS and not t.isdigit()]
    if tokens:
        return tokens[0], ["low_confidence_entity"]
    return "", ["missing_entity"]


class EntityExtractionAgent:
    async def run(self, clean_query: CleanQuery, intent_result: IntentResult) -> RawEntities:
        primary, flags = _extract_primary(clean_query.normalized_text, intent_result.intent)
        entities: List[RawEntity] = []
        if primary:
            entities.append(RawEntity(text=primary, entity_type="product", confidence=0.8))
        return RawEntities(
            entities=entities,
            primary_entity=primary or None,
            ambiguity_flags=flags,
        )
