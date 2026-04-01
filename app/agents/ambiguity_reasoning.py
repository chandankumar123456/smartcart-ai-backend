"""Ambiguity reasoning agent with delayed-resolution strategy."""

from __future__ import annotations

from app.data.models import AmbiguityDecision, IntentResult, NormalizedEntities, QueryIntent, RawEntities

_AMBIGUITY_CONFIDENCE_THRESHOLD = 0.75
_CLEAR_ENTITY_CONFIDENCE_THRESHOLD = 0.85


class AmbiguityReasoningAgent:
    async def run(
        self,
        intent_result: IntentResult,
        raw_entities: RawEntities,
        normalized_entities: NormalizedEntities,
    ) -> AmbiguityDecision:
        candidates = list(dict.fromkeys(raw_entities.candidate_entities))
        lowest_confidence = min((e.confidence for e in normalized_entities.entities), default=1.0)
        single_clear_entity = (
            len(candidates) <= 1
            and len(normalized_entities.entities) == 1
            and lowest_confidence >= _CLEAR_ENTITY_CONFIDENCE_THRESHOLD
            and not raw_entities.ambiguity_flags
            and intent_result.intent != QueryIntent.exploratory
        )
        needs_resolution = (
            not single_clear_entity
            and (
                intent_result.intent == QueryIntent.exploratory
                or len(candidates) > 1
                or bool(raw_entities.ambiguity_flags)
                or lowest_confidence < _AMBIGUITY_CONFIDENCE_THRESHOLD
            )
        )
        strategy = "delayed_resolution"
        if intent_result.intent == QueryIntent.exploratory:
            strategy = "exploratory_broad_search"
        elif len(candidates) > 1:
            strategy = "candidate_enumeration"
        elif raw_entities.ambiguity_flags:
            strategy = "confidence_backoff"
        if not needs_resolution:
            strategy = "none"
        confidence = max(0.0, min(1.0, lowest_confidence))
        return AmbiguityDecision(
            needs_resolution=needs_resolution,
            resolution_strategy=strategy,
            candidate_entities=candidates,
            confidence=confidence,
        )
