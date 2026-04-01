"""Evaluation agent for execution quality and retry signaling."""

from __future__ import annotations

from app.data.models import EvaluationResult, FinalResponse, FinalStructuredQuery

_MIN_RESULTS_THRESHOLD = 1


class EvaluationAgent:
    async def run(self, parsed: FinalStructuredQuery, response: FinalResponse) -> EvaluationResult:
        failures = []
        corrections = []

        if not parsed.domain_guard.allowed:
            return EvaluationResult(success=True, should_retry=False)

        if parsed.constraints.conflict_notes:
            failures.append("constraint_conflict")
            corrections.append("rebalance_preference_weights")

        if parsed.ambiguity.needs_resolution and not response.results:
            failures.append("ambiguity_failure")
            corrections.append("branch_with_candidate_entities")

        if response.results and len(response.results) < _MIN_RESULTS_THRESHOLD:
            failures.append("poor_match_quality")
            corrections.append("expand_entity_variants")

        if parsed.constraints.budget and response.best_option:
            amount = float(parsed.constraints.budget.get("amount", 0))
            price = float(response.best_option.get("price", 0))
            if amount > 0 and price > amount:
                failures.append("constraint_violation")
                corrections.append("enforce_budget_hard_limit")

        should_retry = bool(failures)
        return EvaluationResult(
            success=not should_retry,
            should_retry=should_retry,
            failure_signals=failures,
            correction_suggestions=corrections,
        )
