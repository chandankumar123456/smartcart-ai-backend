"""Learning feedback loop for query intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.agents.synonym_memory import SynonymMemoryAgent
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

    async def learn_from_success(self, parsed: FinalStructuredQuery) -> None:
        for entity in parsed.normalized_entities.entities:
            if entity.raw_text and entity.canonical_name:
                await self._synonym_memory.remember(entity.raw_text, entity.canonical_name)

    async def apply_feedback(self, feedback: LearningFeedback) -> Optional[str]:
        if feedback.accepted and feedback.raw_term and feedback.canonical_name:
            await self._synonym_memory.remember(feedback.raw_term, feedback.canonical_name)
            return feedback.canonical_name
        return None
