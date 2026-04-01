"""Shared persistent memory accessible by all agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.cache.redis_cache import get_cache


class SharedMemory:
    def __init__(self) -> None:
        self._cache = get_cache()
        self._user_prefix = "shared_user_model"
        self._strategy_prefix = "shared_strategy"
        self._product_prefix = "shared_product_rel"

    async def get_user_model(self, user_id: str) -> Dict[str, Any]:
        return await self._cache.get(self._user_prefix, user_id) or {}

    async def update_user_model(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = await self.get_user_model(user_id)
        merged = {**current, **updates, "updated_at": datetime.now(timezone.utc).isoformat()}
        await self._cache.set(self._user_prefix, user_id, merged)
        return merged

    async def get_strategy(self, strategy_key: str) -> Dict[str, Any]:
        return await self._cache.get(self._strategy_prefix, strategy_key) or {}

    async def update_strategy(self, strategy_key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = await self.get_strategy(strategy_key)
        merged = {**current, **updates, "updated_at": datetime.now(timezone.utc).isoformat()}
        await self._cache.set(self._strategy_prefix, strategy_key, merged)
        return merged

    async def get_product_relationships(self, key: str) -> Dict[str, Any]:
        return await self._cache.get(self._product_prefix, key) or {}

    async def update_product_relationships(self, key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = await self.get_product_relationships(key)
        merged = {**current, **updates, "updated_at": datetime.now(timezone.utc).isoformat()}
        await self._cache.set(self._product_prefix, key, merged)
        return merged


_shared_memory: SharedMemory | None = None


def get_shared_memory() -> SharedMemory:
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = SharedMemory()
    return _shared_memory
