"""Redis Cache Layer.

Caches frequent query results to reduce latency and LLM costs.

Flow: User → API → Redis (hit?) → (miss) DB / Agent Pipeline → Response → Redis write

README
------
Reduces latency for repeated queries. Falls back gracefully if Redis unavailable.
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _make_key(prefix: str, data: str) -> str:
    """Create a deterministic cache key from prefix and data."""
    digest = hashlib.sha256(data.encode()).hexdigest()[:16]
    return f"smartcart:{prefix}:{digest}"


class CacheLayer:
    """Async-compatible Redis cache with graceful degradation.

    If Redis is not available, all cache operations become no-ops so the
    pipeline continues without caching.
    """

    def __init__(self, redis_url: str, ttl_seconds: int = 300) -> None:
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._client: Optional[Any] = None
        self._available = False

    async def connect(self) -> None:
        """Attempt to connect to Redis. Silently continues if unavailable."""
        try:
            import redis.asyncio as aioredis  # type: ignore

            self._client = await aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await self._client.ping()
            self._available = True
            logger.info("Redis cache connected: %s", self._redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — caching disabled.", exc)
            self._available = False

    async def disconnect(self) -> None:
        if self._client and self._available:
            await self._client.aclose()

    async def get(self, prefix: str, query: str) -> Optional[Dict[str, Any]]:
        """Return cached value or None on miss / error."""
        if not self._available:
            return None
        try:
            key = _make_key(prefix, query)
            raw = await self._client.get(key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("Cache get error: %s", exc)
        return None

    async def set(self, prefix: str, query: str, value: Dict[str, Any]) -> None:
        """Store a value in cache. Silently ignores errors."""
        if not self._available:
            return
        try:
            key = _make_key(prefix, query)
            await self._client.set(key, json.dumps(value), ex=self._ttl)
        except Exception as exc:
            logger.debug("Cache set error: %s", exc)

    async def invalidate(self, prefix: str, query: str) -> None:
        """Delete a specific cache entry."""
        if not self._available:
            return
        try:
            key = _make_key(prefix, query)
            await self._client.delete(key)
        except Exception as exc:
            logger.debug("Cache invalidate error: %s", exc)

    @property
    def is_available(self) -> bool:
        return self._available


# Module-level singleton
_cache: Optional[CacheLayer] = None


def get_cache() -> CacheLayer:
    from app.core.config import get_settings

    global _cache
    if _cache is None:
        s = get_settings()
        _cache = CacheLayer(s.redis_url, s.cache_ttl_seconds)
    return _cache
