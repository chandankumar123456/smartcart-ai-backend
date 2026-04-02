"""Unit tests for collaborative controller behavior."""

from unittest.mock import AsyncMock

import pytest

from app.agents.controller import ControllerAgent


@pytest.mark.asyncio
async def test_controller_falls_back_when_llm_reasoning_fails():
    mock_llm = AsyncMock()
    mock_llm.call.side_effect = Exception("LLM unavailable")
    controller = ControllerAgent(max_retries=2, llm_manager=mock_llm)

    update = await controller.act(
        {
            "structured_query": {"product": "milk"},
            "normalized_item": {"canonical_name": "milk"},
            "unified_product": {"platforms": []},
            "match_quality": "weak",
            "retry_count": 0,
            "max_retries": 2,
            "decision_trace": [],
            "tool_trace": [],
            "current_entity": "milk",
        }
    )

    assert update["next_action"] == "enrichment_node"
    assert update["collaborative_proposals"] == []
    assert update["collaborative_critiques"] == []
    assert update["synthesis_trace"]["consensus"] == "fallback"
    assert update["decision_trace"][-1]["decision_source"] == "deterministic_fallback"

