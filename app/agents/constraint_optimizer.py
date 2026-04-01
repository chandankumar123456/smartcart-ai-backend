"""Constraint optimization agent for multi-objective grocery decisions."""

from __future__ import annotations

from typing import Dict, List

from app.data.models import PlatformProduct


class ConstraintOptimizerAgent:
    """Turns constraints/preferences into optimization weights and objective scores."""

    def derive_weights(
        self,
        base_weights: Dict[str, float],
        preferences: List[str],
        user_preferences: List[str],
    ) -> Dict[str, float]:
        weights = dict(base_weights or {"price": 0.4, "delivery": 0.3, "rating": 0.2, "discount": 0.1})
        pref = set([*preferences, *user_preferences])
        if "cheap" in pref or "budget" in pref:
            weights["price"] = max(weights.get("price", 0.4), 0.6)
            weights["rating"] = min(weights.get("rating", 0.2), 0.15)
        if "premium" in pref:
            weights["rating"] = max(weights.get("rating", 0.2), 0.4)
        if "fresh" in pref:
            weights["delivery"] = max(weights.get("delivery", 0.3), 0.35)
        total = sum(weights.values()) or 1.0
        return {k: round(v / total, 4) for k, v in weights.items()}

    def score_candidate(self, product: PlatformProduct, budget_limit: float | None) -> float:
        budget_score = self._compute_budget_score(product.price, budget_limit)
        stock_score = 1.0 if product.in_stock else 0.0
        return round(0.7 * budget_score + 0.3 * stock_score, 4)

    @staticmethod
    def _compute_budget_score(price: float, budget_limit: float | None) -> float:
        numeric_budget: float | None
        try:
            numeric_budget = float(budget_limit) if budget_limit is not None else None
        except (TypeError, ValueError):
            numeric_budget = None
        budget_score = 1.0
        if numeric_budget and numeric_budget > 0:
            budget_score = 1.0 if price <= numeric_budget else max(0.0, 1 - ((price - numeric_budget) / numeric_budget))
        return budget_score
