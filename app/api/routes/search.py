"""Search and parse endpoints.

README
------
Primary endpoints:
- POST /parse-query → intelligence layer output
- POST /search → execution layer (matching + ranking)
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.api.request_handler import SearchRequest
from app.cache.redis_cache import get_cache
from app.core.security import check_rate_limit, verify_api_key
from app.data.models import FinalResponse, FinalStructuredQuery
from app.orchestrator.pipeline import get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/parse-query",
    response_model=FinalStructuredQuery,
    summary="Parse grocery query into structured intelligence",
    description=(
        "Runs the strict intelligence pipeline "
        "(language processing → intent detection → entity extraction → normalization "
        "→ constraint extraction → domain guard → fallback → output formatter) "
        "and returns machine-usable structured query JSON."
    ),
)
async def parse_query(
    body: SearchRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> FinalStructuredQuery:
    check_rate_limit(request)
    pipeline = get_pipeline()
    return await pipeline.parse_query(body.query)


@router.post(
    "/search",
    response_model=FinalResponse,
    summary="Search and compare grocery prices across platforms",
    description=(
        "Accepts a natural language query, first runs /parse-query intelligence stage, "
        "then executes matching/ranking/deals on finalized structured query, "
        "and returns structured results with the best option and available deals."
    ),
)
async def search(
    body: FinalStructuredQuery,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> FinalResponse:
    check_rate_limit(request)
    cache = get_cache()
    cache_key = body.structured_query.normalized_query or body.clean_query.normalized_text
    cached = await cache.get("search", cache_key)
    if cached:
        logger.debug("Cache hit for query: %s", cache_key)
        return FinalResponse(**cached)

    pipeline = get_pipeline()
    result = await pipeline.run_search(body)

    await cache.set("search", cache_key, result.model_dump())
    return result
