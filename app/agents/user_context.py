"""User context agent for personalization-aware planning and ranking."""

from __future__ import annotations

from collections import Counter

from app.data.models import CleanQuery, UserContext
from app.memory.shared import get_shared_memory


class UserContextAgent:
    def __init__(self) -> None:
        self._shared_memory = get_shared_memory()

    async def run(self, clean_query: CleanQuery) -> UserContext:
        text = clean_query.normalized_text
        preferences = []
        dietary_patterns = []
        budget_habits = {}
        user_id = "anonymous"
        profile = await self._shared_memory.get_user_model(user_id)
        long_term_preferences = dict(profile.get("long_term_preferences", {}))
        consumption_habits = dict(profile.get("consumption_habits", {}))
        platform_affinity = dict(profile.get("platform_affinity", {}))
        predicted_needs = list(profile.get("predicted_needs", []))

        if "vegan" in text:
            dietary_patterns.append("vegan")
        if "vegetarian" in text or any(token == "veg" for token in clean_query.tokens):
            dietary_patterns.append("vegetarian")
        if "organic" in text:
            preferences.append("organic")
        if "cheap" in text or "budget" in text:
            budget_habits["price_sensitivity"] = "high"
        if preferences:
            for pref in preferences:
                long_term_preferences[pref] = round(float(long_term_preferences.get(pref, 0.0)) + 0.1, 4)
        token_counts = Counter([t for t in clean_query.tokens if len(t) > 2])
        for token, count in token_counts.items():
            consumption_habits[token] = round(float(consumption_habits.get(token, 0.0)) + (count * 0.05), 4)
        if not predicted_needs and consumption_habits:
            predicted_needs = [k for k, _ in sorted(consumption_habits.items(), key=lambda kv: kv[1], reverse=True)[:3]]
        if not platform_affinity:
            platform_affinity = {"blinkit": 0.5, "zepto": 0.5}
        await self._shared_memory.update_user_model(
            user_id,
            {
                "long_term_preferences": long_term_preferences,
                "consumption_habits": consumption_habits,
                "platform_affinity": platform_affinity,
                "predicted_needs": predicted_needs,
                "budget_habits": budget_habits,
            },
        )
        behavior_summary = {
            "clicks": profile.get("clicks", 0),
            "purchases": profile.get("purchases", 0),
            "ignored": profile.get("ignored", 0),
            "ctr": profile.get("ctr", 0.0),
        }

        return UserContext(
            user_id=user_id,
            preferences=preferences,
            dietary_patterns=dietary_patterns,
            budget_habits=budget_habits,
            historical_behavior=behavior_summary,
            long_term_preferences=long_term_preferences,
            consumption_habits=consumption_habits,
            platform_affinity=platform_affinity,
            predicted_needs=predicted_needs,
        )
