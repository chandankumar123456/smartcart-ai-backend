"""Collaborative reasoning helpers for controller-led search execution."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, Field


class ControllerProposal(BaseModel):
    role: str
    action: str
    rationale: str = ""
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)


class ProposalCritique(BaseModel):
    critic_role: str
    proposal_action: str
    score: float = 0.0
    verdict: str = "neutral"
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_adjustments: list[str] = Field(default_factory=list)


class ControllerSynthesis(BaseModel):
    action: str
    rationale: str = ""
    confidence: float = 0.0
    consensus: str = "fallback"
    score_breakdown: dict[str, float] = Field(default_factory=dict)


def _clamp_score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


class ProposalAgent:
    """Collects a candidate controller action from an LLM perspective."""

    def __init__(self, *, llm_manager: Any, role: str, focus: str) -> None:
        self._llm_manager = llm_manager
        self._role = role
        self._focus = focus

    async def act(self, state: Mapping[str, Any]) -> ControllerProposal:
        schema_example = json.dumps(
            {
                "role": self._role,
                "action": state["fallback_action"],
                "rationale": "Short justification grounded in the runtime state.",
                "confidence": 0.72,
                "evidence": ["state signal 1", "state signal 2"],
            }
        )
        prompt = (
            "collaborative controller proposal\n"
            f"Role: {self._role}\n"
            f"Focus: {self._focus}\n"
            "Choose exactly one action from available_actions.\n"
            "Return strict JSON only.\n"
            f"State:\n{json.dumps(dict(state), default=str, sort_keys=True)}"
        )
        result = await self._llm_manager.call(prompt, schema_example=schema_example)
        proposal = ControllerProposal.model_validate(
            {
                "role": result.get("role") or self._role,
                "action": result.get("action", ""),
                "rationale": result.get("rationale", ""),
                "confidence": _clamp_score(result.get("confidence", 0.0)),
                "evidence": result.get("evidence", []),
            }
        )
        return proposal


class CritiqueAgent:
    """Scores an individual controller proposal."""

    def __init__(self, *, llm_manager: Any, role: str, focus: str) -> None:
        self._llm_manager = llm_manager
        self._role = role
        self._focus = focus

    async def act(self, state: Mapping[str, Any]) -> ProposalCritique:
        schema_example = json.dumps(
            {
                "critic_role": self._role,
                "proposal_action": state["proposal"]["action"],
                "score": 0.68,
                "verdict": "support",
                "strengths": ["Action is feasible"],
                "risks": ["May terminate too early"],
                "recommended_adjustments": ["Validate ranking before terminating"],
            }
        )
        prompt = (
            "collaborative controller critique\n"
            f"Role: {self._role}\n"
            f"Focus: {self._focus}\n"
            "Review the proposal against the current runtime state and available actions.\n"
            "Return strict JSON only.\n"
            f"State:\n{json.dumps(dict(state), default=str, sort_keys=True)}"
        )
        result = await self._llm_manager.call(prompt, schema_example=schema_example)
        critique = ProposalCritique.model_validate(
            {
                "critic_role": result.get("critic_role") or self._role,
                "proposal_action": result.get("proposal_action", state["proposal"]["action"]),
                "score": _clamp_score(result.get("score", 0.0)),
                "verdict": result.get("verdict", "neutral"),
                "strengths": result.get("strengths", []),
                "risks": result.get("risks", []),
                "recommended_adjustments": result.get("recommended_adjustments", []),
            }
        )
        return critique


class SynthesisAgent:
    """Combines collaborative proposals and critiques into a final action."""

    def __init__(self, *, llm_manager: Any) -> None:
        self._llm_manager = llm_manager

    async def act(self, state: Mapping[str, Any]) -> ControllerSynthesis:
        schema_example = json.dumps(
            {
                "action": state["fallback_action"],
                "rationale": "Summarize why this action best fits the current state.",
                "confidence": 0.75,
                "consensus": "majority_support",
                "score_breakdown": {"response_node": 0.12, state["fallback_action"]: 0.79},
            }
        )
        prompt = (
            "collaborative controller synthesis\n"
            "Select the final controller action using proposal consensus and critique scores.\n"
            "Return strict JSON only.\n"
            f"State:\n{json.dumps(dict(state), default=str, sort_keys=True)}"
        )
        result = await self._llm_manager.call(prompt, schema_example=schema_example)
        synthesis = ControllerSynthesis.model_validate(
            {
                "action": result.get("action", ""),
                "rationale": result.get("rationale", ""),
                "confidence": _clamp_score(result.get("confidence", 0.0)),
                "consensus": result.get("consensus", "fallback"),
                "score_breakdown": {
                    action: _clamp_score(score)
                    for action, score in (result.get("score_breakdown") or {}).items()
                },
            }
        )
        return synthesis


def score_actions(
    proposals: Sequence[ControllerProposal],
    critiques: Sequence[ProposalCritique],
    available_actions: Sequence[str],
    fallback_action: str,
) -> dict[str, float]:
    """Derive deterministic action scores from proposal confidence and critiques."""

    scores = {action: 0.0 for action in available_actions}
    for proposal in proposals:
        if proposal.action in scores:
            scores[proposal.action] += proposal.confidence
    for critique in critiques:
        if critique.proposal_action in scores:
            scores[critique.proposal_action] += critique.score
    if fallback_action in scores and all(value <= 0.0 for value in scores.values()):
        scores[fallback_action] = 1.0
    return {action: round(score, 4) for action, score in scores.items()}
