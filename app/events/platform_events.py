"""Event-driven platform intelligence integration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.data.models import PlatformEvent, PlatformEventType
from app.memory.shared import get_shared_memory


class PlatformEventIntelligence:
    def __init__(self) -> None:
        self._memory = get_shared_memory()

    async def ingest(self, event: PlatformEvent) -> Dict[str, Any]:
        event_timestamp = event.timestamp or datetime.now(timezone.utc).isoformat()
        payload = dict(event.payload)
        await self._ingest_cross_service_signals(payload, event_timestamp)
        if event.event_type == PlatformEventType.user_behavior:
            return await self._handle_user_behavior(event.user_id, payload, event_timestamp)
        if event.event_type == PlatformEventType.order_created:
            return await self._handle_order_created(event.user_id, payload, event_timestamp)
        if event.event_type in {PlatformEventType.inventory_updated, PlatformEventType.price_updated}:
            return await self._handle_market_update(event.event_type, payload, event_timestamp)
        return {"accepted": False, "reason": "unsupported_event_type"}

    async def _handle_user_behavior(self, user_id: str, payload: Dict[str, Any], ts: str) -> Dict[str, Any]:
        model = await self._memory.get_user_model(user_id)
        actions = model.get("behavior_actions", [])
        actions.append({"action": payload.get("action", "unknown"), "item": payload.get("item"), "ts": ts})
        actions = actions[-50:]
        clicks = int(model.get("clicks", 0)) + (1 if payload.get("action") == "click" else 0)
        purchases = int(model.get("purchases", 0)) + (1 if payload.get("action") == "purchase" else 0)
        ignored = int(model.get("ignored", 0)) + (1 if payload.get("action") == "ignore" else 0)
        ctr = round(clicks / max(1, clicks + ignored), 4)
        profile = await self._memory.update_user_model(
            user_id,
            {"behavior_actions": actions, "clicks": clicks, "purchases": purchases, "ignored": ignored, "ctr": ctr},
        )
        return {"accepted": True, "kind": "user_behavior", "user_model": profile}

    async def _handle_order_created(self, user_id: str, payload: Dict[str, Any], ts: str) -> Dict[str, Any]:
        model = await self._memory.get_user_model(user_id)
        history = model.get("purchase_history", {})
        for item in payload.get("items", []):
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip().lower()
            else:
                name = str(item).strip().lower()
            if name:
                history[name] = int(history.get(name, 0)) + 1
        updated = await self._memory.update_user_model(
            user_id,
            {"purchase_history": history, "last_order_ts": ts},
        )
        return {"accepted": True, "kind": "order_created", "user_model": updated}

    async def _handle_market_update(self, event_type: PlatformEventType, payload: Dict[str, Any], ts: str) -> Dict[str, Any]:
        key = payload.get("entity", "global")
        market = await self._memory.get_strategy("market_signals")
        entity_map = dict(market.get(key, {}))
        if event_type == PlatformEventType.inventory_updated:
            entity_map["in_stock"] = bool(payload.get("in_stock", True))
            entity_map["inventory_ts"] = ts
        if event_type == PlatformEventType.price_updated:
            entity_map["price"] = payload.get("price")
            entity_map["price_ts"] = ts
        market[key] = entity_map
        stored = await self._memory.update_strategy("market_signals", market)
        return {"accepted": True, "kind": event_type.value, "market_signals": stored}

    async def _ingest_cross_service_signals(self, payload: Dict[str, Any], ts: str) -> None:
        recommendation_signals = payload.get("recommendation_signals")
        analytics_signals = payload.get("analytics_signals")
        forecast_signals = payload.get("forecast_signals")
        if not any([recommendation_signals, analytics_signals, forecast_signals]):
            return
        strategy = await self._memory.get_strategy("recommendation_signals")
        if recommendation_signals:
            strategy["recommendation_signals"] = recommendation_signals
        if analytics_signals:
            strategy["analytics_signals"] = analytics_signals
        if forecast_signals:
            strategy["forecast_signals"] = forecast_signals
        strategy["signal_timestamp"] = ts
        await self._memory.update_strategy("recommendation_signals", strategy)


_platform_events: PlatformEventIntelligence | None = None


def get_platform_event_intelligence() -> PlatformEventIntelligence:
    global _platform_events
    if _platform_events is None:
        _platform_events = PlatformEventIntelligence()
    return _platform_events
