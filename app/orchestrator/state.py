"""LangGraph state definitions for agent-driven search execution."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict

from app.data.models import (
    DealResult,
    EvaluationResult,
    FinalResponse,
    FinalStructuredQuery,
    MatchingDiagnostics,
    NormalizedItem,
    PlatformProduct,
    RankingResult,
    StructuredQuery,
    ToolAttempt,
    UnifiedProduct,
)

MatchQuality = Literal["strong", "weak", "empty"]


class SearchGraphState(TypedDict, total=False):
    user_query: str
    structured_query: StructuredQuery
    final_structured_query: FinalStructuredQuery
    current_step: str
    next_action: str
    last_observation: Dict[str, Any]
    normalized_item: NormalizedItem
    unified_product: UnifiedProduct
    preliminary_products: List[PlatformProduct]
    ranked_products: RankingResult
    ranking_result: RankingResult
    deals: DealResult
    deal_result: DealResult
    response: FinalResponse
    diagnostics: MatchingDiagnostics
    retry_count: int
    match_quality: MatchQuality
    tool_trace: List[Dict[str, Any]]
    tool_request: Dict[str, Any]
    tool_result: Dict[str, Any]
    candidate_entities: List[str]
    current_entity: str
    current_path_index: int
    selected_path: str
    evaluation_result: EvaluationResult
    market_signals: Dict[str, Any]
    ranking_preferences: Dict[str, float]
    budget_limit: float | None
    path_history: List[Dict[str, Any]]
    decision_trace: List[Dict[str, Any]]
    tool_attempts: List[ToolAttempt]
    max_retries: int
