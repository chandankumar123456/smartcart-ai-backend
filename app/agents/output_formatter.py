"""Output Formatter Agent."""

from __future__ import annotations

from app.data.models import (
    AmbiguityDecision,
    Constraints,
    DomainGuardResult,
    ExecutionPlan,
    ExecutionGraph,
    CandidateExecutionPath,
    EvaluationFrame,
    FailurePolicy,
    FinalStructuredQuery,
    FallbackDecision,
    IntentResult,
    LearningSignals,
    NormalizedEntities,
    RawEntities,
    StructuredQuery,
    CleanQuery,
    UserContext,
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
        ambiguity: AmbiguityDecision,
        fallback: FallbackDecision,
        execution_plan: ExecutionPlan,
        execution_graph: ExecutionGraph,
        candidate_paths: list[CandidateExecutionPath],
        user_context: UserContext,
        learning_signals: LearningSignals,
        evaluation_history: list[EvaluationFrame],
        failure_policies: list[FailurePolicy],
        structured_query: StructuredQuery,
    ) -> FinalStructuredQuery:
        return FinalStructuredQuery(
            clean_query=clean_query,
            intent_result=intent_result,
            raw_entities=raw_entities,
            normalized_entities=normalized_entities,
            constraints=constraints,
            domain_guard=domain_guard,
            ambiguity=ambiguity,
            fallback=fallback,
            execution_plan=execution_plan,
            execution_graph=execution_graph,
            candidate_paths=candidate_paths,
            user_context=user_context,
            learning_signals=learning_signals,
            evaluation_history=evaluation_history,
            failure_policies=failure_policies,
            structured_query=structured_query,
        )
