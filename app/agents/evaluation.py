"""Evaluation agent for execution quality and retry signaling."""

from __future__ import annotations

from app.data.models import EvaluationResult, FinalResponse, FinalStructuredQuery


class EvaluationAgent:
    async def run(self, parsed: FinalStructuredQuery, response: FinalResponse) -> EvaluationResult:
        failures = []
        corrections = []
        def add_signal(signal: str, correction: str) -> None:
            if signal not in failures:
                failures.append(signal)
            if correction not in corrections:
                corrections.append(correction)

        if not parsed.domain_guard.allowed:
            return EvaluationResult(success=True, should_retry=False)

        if parsed.constraints.conflict_notes:
            add_signal("constraint_conflict", "rebalance_preference_weights")

        if parsed.ambiguity.needs_resolution and not parsed.ambiguity.candidate_entities:
            add_signal("ambiguity_failure", "collect_candidate_entities")

        has_single_clear_entity = (
            len(parsed.normalized_entities.entities) == 1
            and parsed.normalized_entities.entities[0].confidence >= 0.85
            and not parsed.ambiguity.needs_resolution
        )
        if not response.results:
            if has_single_clear_entity:
                corrections.append("mark_entity_unavailable_without_retry")
            else:
                add_signal("ambiguity_failure", "branch_with_candidate_entities")
                add_signal("poor_match_quality", "expand_entity_variants")

        if parsed.constraints.budget and response.best_option:
            amount_raw = parsed.constraints.budget.get("amount")
            price_raw = response.best_option.get("price")
            try:
                amount = float(amount_raw) if amount_raw is not None else 0.0
                price = float(price_raw) if price_raw is not None else 0.0
            except (TypeError, ValueError):
                amount = 0.0
                price = 0.0
            if amount > 0 and price > amount:
                add_signal("constraint_violation", "enforce_budget_hard_limit")

        quality_score = 1.0
        quality_score -= min(0.6, len(failures) * 0.2)
        if response.results:
            quality_score += min(0.2, len(response.results) * 0.02)
        should_retry = bool(failures)
        return EvaluationResult(
            success=not should_retry,
            should_retry=should_retry,
            failure_signals=failures,
            correction_suggestions=corrections,
            quality_score=max(0.0, min(1.0, round(quality_score, 4))),
        )
