"""Domain Guard Agent."""

from __future__ import annotations

from app.data.models import CleanQuery, DomainGuardResult, IntentResult, QueryIntent


class DomainGuardAgent:
    """Prevents unsupported domain queries from execution layer."""

    async def run(self, clean_query: CleanQuery, intent_result: IntentResult) -> DomainGuardResult:
        if intent_result.intent == QueryIntent.unsupported:
            return DomainGuardResult(
                allowed=False,
                confidence=max(intent_result.confidence, 0.9),
                reason="Query is outside grocery assistant domain",
            )
        if not clean_query.normalized_text.strip():
            return DomainGuardResult(allowed=False, confidence=1.0, reason="Empty normalized query")
        return DomainGuardResult(allowed=True, confidence=0.95, reason="Within grocery domain")
