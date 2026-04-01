"""Output Formatter Agent."""

from __future__ import annotations

from app.data.models import (
    Constraints,
    DomainGuardResult,
    FinalStructuredQuery,
    FallbackDecision,
    IntentResult,
    NormalizedEntities,
    RawEntities,
    StructuredQuery,
    CleanQuery,
)


class OutputFormatterAgent:
    async def run(
        self,
        clean_query: CleanQuery,
        intent_result: IntentResult,
        raw_entities: RawEntities,
        normalized_entities: NormalizedEntities,
        constraints: Constraints,
        domain_guard: DomainGuardResult,
        fallback: FallbackDecision,
        structured_query: StructuredQuery,
    ) -> FinalStructuredQuery:
        return FinalStructuredQuery(
            clean_query=clean_query,
            intent_result=intent_result,
            raw_entities=raw_entities,
            normalized_entities=normalized_entities,
            constraints=constraints,
            domain_guard=domain_guard,
            fallback=fallback,
            structured_query=structured_query,
        )
