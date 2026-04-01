"""Entity Extraction Agent."""

from __future__ import annotations

from typing import List, Tuple

from app.data.models import CleanQuery, IntentResult, QueryIntent, RawEntities, RawEntity

_KNOWN_PRODUCTS = {
    "milk", "bread", "eggs", "rice", "tomato", "onion", "oil", "butter",
    "pasta", "sugar", "atta", "flour", "salt", "tea", "coffee", "biscuits",
    "chips", "noodles", "cheese", "yogurt", "curd", "chicken", "ghee", "paneer",
    "snacks", "salad", "ginger", "lentils", "cumin seeds", "red chili powder",
    "wheat flour", "cucumber", "garlic", "mayonnaise", "mayo",
}
_STOPWORDS = {"find", "show", "get", "buy", "need", "want", "for", "me", "the", "a", "an"}
_DEFAULT_ENTITY_CONFIDENCE = 0.8


def _extract_primary(q: str, tokens: List[str], intent: QueryIntent) -> Tuple[str, List[str]]:
    if intent == QueryIntent.unsupported:
        return "", []
    if intent == QueryIntent.exploratory:
        return "snacks", ["query_is_exploratory"]
    for product in _KNOWN_PRODUCTS:
        if product in q:
            return product, []
    filtered_tokens = [t for t in tokens if t not in _STOPWORDS and not t.isdigit()]
    if filtered_tokens:
        return filtered_tokens[0], ["low_confidence_entity"]
    return "", ["missing_entity"]


class EntityExtractionAgent:
    async def run(self, clean_query: CleanQuery, intent_result: IntentResult) -> RawEntities:
        primary, flags = _extract_primary(
            clean_query.normalized_text,
            clean_query.tokens,
            intent_result.intent,
        )
        candidate_entities = []
        if " and " in clean_query.normalized_text:
            for token in clean_query.normalized_text.split(" and "):
                token = token.strip()
                if any(product in token for product in _KNOWN_PRODUCTS):
                    candidate_entities.append(token)
        if primary and primary not in candidate_entities:
            candidate_entities.insert(0, primary)
        entities: List[RawEntity] = []
        if primary:
            entities.append(
                RawEntity(
                    text=primary,
                    entity_type="product",
                    confidence=_DEFAULT_ENTITY_CONFIDENCE,
                )
            )
        return RawEntities(
            entities=entities,
            primary_entity=primary or None,
            ambiguity_flags=flags,
            candidate_entities=candidate_entities,
        )
