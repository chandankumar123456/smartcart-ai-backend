"""Fallback Agent."""

from __future__ import annotations

from app.data.models import FallbackDecision, NormalizedEntities, QueryIntent


class FallbackAgent:
    async def run(self, normalized_entities: NormalizedEntities, intent: QueryIntent) -> FallbackDecision:
        if intent == QueryIntent.exploratory:
            return FallbackDecision(
                used=True,
                mode="exploratory_mode",
                reason="User query is vague; using exploratory handling",
                alternatives=["snacks", "milk", "rice"],
            )
        if normalized_entities.unresolved_entities:
            return FallbackDecision(
                used=True,
                mode="ambiguity",
                reason="Some entities could not be normalized confidently",
                alternatives=normalized_entities.unresolved_entities,
            )
        return FallbackDecision(used=False, mode="none", reason="", alternatives=[])
