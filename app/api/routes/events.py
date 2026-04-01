"""Platform event ingestion routes for continuous learning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.security import check_rate_limit, verify_api_key
from app.data.models import PlatformEvent
from app.events.platform_events import get_platform_event_intelligence

router = APIRouter()


@router.post(
    "/platform-events",
    summary="Ingest platform intelligence events",
    description=(
        "Consumes real-time platform events (user behavior, orders, inventory, pricing) "
        "to continuously update shared memory, personalization, and decision strategies."
    ),
)
async def ingest_platform_event(
    body: PlatformEvent,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> dict:
    check_rate_limit(request)
    intelligence = get_platform_event_intelligence()
    return await intelligence.ingest(body)
