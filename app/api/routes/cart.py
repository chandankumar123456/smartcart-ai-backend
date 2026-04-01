"""POST /cart-optimization — Multi-platform cart cost optimisation endpoint.

README
------
Accepts a list of grocery items and finds the optimal platform split that
minimises total cart cost, comparing single-platform vs. split-order strategies.
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.api.request_handler import CartOptimizeRequest
from app.core.security import check_rate_limit, verify_api_key
from app.data.models import FinalResponse
from app.orchestrator.pipeline import get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/cart-optimization",
    response_model=FinalResponse,
    summary="Optimise cart cost across multiple platforms",
    description=(
        "Accepts a list of grocery items, compares prices across all platforms, "
        "and returns the optimal split-order strategy that minimises total cart cost, "
        "along with per-platform subtotals and total savings."
    ),
)
async def cart_optimize(
    body: CartOptimizeRequest,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> FinalResponse:
    check_rate_limit(request)
    pipeline = get_pipeline()
    result = await pipeline.run_cart_optimize(body.items)
    return result
