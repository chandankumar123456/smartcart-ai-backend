"""POST /ai/recipe — Food planning → grocery conversion endpoint.

README
------
Accepts a recipe query, generates an ingredient list, maps ingredients to
available products across platforms, and returns an optimised shopping list
with cost estimate.
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.api.request_handler import RecipeRequest
from app.cache.redis_cache import get_cache
from app.core.security import check_rate_limit, verify_api_key
from app.data.models import FinalResponse
from app.orchestrator.pipeline import get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/recipe",
    response_model=FinalResponse,
    summary="Convert a recipe into a grocery shopping list",
    description=(
        "Accepts a recipe name or description, generates ingredients adjusted for "
        "the requested servings, maps each ingredient to available products across "
        "platforms, and returns an optimised shopping list with total cost estimate."
    ),
)
async def recipe(
    body: RecipeRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> FinalResponse:
    check_rate_limit(request)
    cache_key = f"{body.query}|servings={body.servings}"
    cache = get_cache()
    cached = await cache.get("recipe", cache_key)
    if cached:
        logger.debug("Cache hit for recipe: %s", body.query)
        return FinalResponse(**cached)

    pipeline = get_pipeline()
    result = await pipeline.run_recipe(body.query, servings=body.servings)

    await cache.set("recipe", cache_key, result.model_dump())
    return result
