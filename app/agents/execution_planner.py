"""Adaptive execution planner for multi-intent orchestration."""

from __future__ import annotations

from app.data.models import ExecutionPlan, IntentResult, QueryIntent


class ExecutionPlannerAgent:
    async def run(self, intent_result: IntentResult) -> ExecutionPlan:
        primary = intent_result.intent
        secondary = set(intent_result.secondary_intents)

        if primary == QueryIntent.recipe and QueryIntent.cart_optimization in secondary:
            return ExecutionPlan(
                mode="recipe_then_cart_optimization",
                steps=["recipe_generation", "ingredient_matching", "cart_optimization"],
                reason="Recipe intent with optimization request detected",
            )
        if primary == QueryIntent.recipe:
            return ExecutionPlan(
                mode="recipe_only",
                steps=["recipe_generation", "ingredient_matching"],
                reason="Primary recipe intent",
            )
        if primary == QueryIntent.cart_optimization:
            return ExecutionPlan(
                mode="cart_optimization_only",
                steps=["cart_lookup", "split_optimization"],
                reason="Primary cart optimization intent",
            )
        return ExecutionPlan(
            mode="search_only",
            steps=["matching", "ranking", "deal_detection"],
            reason="Primary search/exploratory intent",
        )
