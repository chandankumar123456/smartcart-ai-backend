"""Learning feedback loop for query intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.agents.synonym_memory import SynonymMemoryAgent
from app.cache.redis_cache import get_cache
from app.data.models import FinalStructuredQuery


@dataclass
class LearningFeedback:
    raw_term: str
    canonical_name: str
    accepted: bool = True
    reason: str = ""


class LearningLoop:
    def __init__(self, synonym_memory: SynonymMemoryAgent) -> None:
        self._synonym_memory = synonym_memory
        self._cache = get_cache()
        self._policy_prefix = "learning_policy"

    async def learn_from_success(self, parsed: FinalStructuredQuery) -> None:
        for entity in parsed.normalized_entities.entities:
            if entity.raw_text and entity.canonical_name:
                await self._synonym_memory.remember(entity.raw_text, entity.canonical_name)
        await self._persist_policy_update(parsed, success=True)

    async def apply_feedback(self, feedback: LearningFeedback) -> Optional[str]:
        if feedback.accepted and feedback.raw_term and feedback.canonical_name:
            await self._synonym_memory.remember(feedback.raw_term, feedback.canonical_name)
            return feedback.canonical_name
        return None

    async def learn_from_outcome(self, parsed: FinalStructuredQuery, success: bool) -> None:
        await self._persist_policy_update(parsed, success=success)

    async def load_policy(self, normalized_query: str) -> dict:
        cached = await self._cache.get(self._policy_prefix, normalized_query)
        return cached or {}

    async def _persist_policy_update(self, parsed: FinalStructuredQuery, success: bool) -> None:
        key = parsed.clean_query.normalized_text
        existing = await self.load_policy(key)
        policy = {
            "query": key,
            "success_count": int(existing.get("success_count", 0)) + (1 if success else 0),
            "failure_count": int(existing.get("failure_count", 0)) + (0 if success else 1),
            "ranking_adjustments": parsed.learning_signals.ranking_adjustments,
            "notes": parsed.learning_signals.evaluation_notes[-5:],
        }
        await self._cache.set(self._policy_prefix, key, policy)
