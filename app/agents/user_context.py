"""User context agent for personalization-aware planning and ranking."""

from __future__ import annotations

from app.data.models import CleanQuery, UserContext


class UserContextAgent:
    async def run(self, clean_query: CleanQuery) -> UserContext:
        text = clean_query.normalized_text
        preferences = []
        dietary_patterns = []
        budget_habits = {}

        if "vegan" in text:
            dietary_patterns.append("vegan")
        if "vegetarian" in text or "veg" in clean_query.tokens:
            dietary_patterns.append("vegetarian")
        if "organic" in text:
            preferences.append("organic")
        if "cheap" in text or "budget" in text:
            budget_habits["price_sensitivity"] = "high"

        return UserContext(
            user_id="anonymous",
            preferences=preferences,
            dietary_patterns=dietary_patterns,
            budget_habits=budget_habits,
            historical_behavior={},
        )
