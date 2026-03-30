"""POST /ai/search — Primary search + price comparison endpoint.

README
------
Primary endpoint for product search and cross-platform price comparison.
Runs: QueryUnderstanding → ProductMatching → Ranking → DealDetection
Returns: FinalResponse JSON
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.api.request_handler import SearchRequest
from app.cache.redis_cache import get_cache
from app.core.security import check_rate_limit, verify_api_key
from app.data.models import FinalResponse
from app.orchestrator.pipeline import get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/search",
    response_model=FinalResponse,
    summary="Search and compare grocery prices across platforms",
    description=(
        "Accepts a natural language query, runs the full multi-agent pipeline "
        "(query understanding → product matching → ranking → deal detection), "
        "and returns structured results with the best option and available deals."
    ),
)
async def search(
    body: SearchRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> FinalResponse:
    check_rate_limit(request)
    cache = get_cache()
    cached = await cache.get("search", body.query)
    if cached:
        logger.debug("Cache hit for query: %s", body.query)
        return FinalResponse(**cached)

    pipeline = get_pipeline()
    result = await pipeline.run_search(body.query)

    await cache.set("search", body.query, result.model_dump())
    return result
