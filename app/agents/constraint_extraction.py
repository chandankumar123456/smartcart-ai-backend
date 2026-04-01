"""Constraint Extraction Agent."""

from __future__ import annotations

import re
from typing import Dict

from app.data.models import CleanQuery, Constraints

_PRICE_PATTERN = re.compile(r"(?:under|below|less than|<|max|upto)\s*(?:rs\.?|₹)?\s*(\d+(?:\.\d+)?)", re.I)
_SERVINGS_PATTERN = re.compile(r"(?:for|serves?)\s*(\d+)\s*(?:people|persons|servings?)?", re.I)
_PREFERENCE_KEYWORDS = {
    "cheap": "cheap",
    "budget": "cheap",
    "organic": "organic",
    "healthy": "healthy",
    "premium": "premium",
    "fresh": "fresh",
}
_DEFAULT_RANKING_WEIGHTS = {"price": 0.4, "delivery": 0.3, "rating": 0.2, "discount": 0.1}
_CHEAP_PRICE_WEIGHT = 0.6
_HEALTHY_RATING_WEIGHT = 0.35
_BASE_SERVINGS = 2.0


class ConstraintExtractionAgent:
    async def run(self, clean_query: CleanQuery) -> Constraints:
        q = clean_query.normalized_text
        budget_match = _PRICE_PATTERN.search(q)
        budget = (
            {"operator": "under", "amount": float(budget_match.group(1)), "currency": "INR"}
            if budget_match
            else None
        )
        servings_match = _SERVINGS_PATTERN.search(q)
        servings = int(servings_match.group(1)) if servings_match else None
        words = set(clean_query.tokens)
        preferences = []
        seen_preferences = set()
        for key, value in _PREFERENCE_KEYWORDS.items():
            if key in words and value not in seen_preferences:
                seen_preferences.add(value)
                preferences.append(value)

        ranking_weights: Dict[str, float] = {}
        if "cheap" in preferences:
            ranking_weights["price"] = _CHEAP_PRICE_WEIGHT
        if "organic" in preferences or "healthy" in preferences:
            ranking_weights["rating"] = _HEALTHY_RATING_WEIGHT
        if not ranking_weights:
            ranking_weights = _DEFAULT_RANKING_WEIGHTS.copy()

        quantity_multiplier = float(servings) / _BASE_SERVINGS if servings and servings > 0 else 1.0
        return Constraints(
            budget=budget,
            servings=servings,
            preferences=preferences,
            inferred_quantity_multiplier=quantity_multiplier,
            ranking_preference_weights=ranking_weights,
        )
