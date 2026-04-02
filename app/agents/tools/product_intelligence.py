"""Agent-level product intelligence tools and mapping helpers."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

import app.data.layer as data_layer
from app.cache.redis_cache import get_cache
from app.core.config import get_settings
from app.data.models import Platform, PlatformProduct, ToolAttempt
from app.scrapers.blinkit_scraper import _extract_from_html

logger = logging.getLogger(__name__)
_UNIT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s?(?:kg|g|mg|l|ml|pcs|pc|pack|packs)\b", re.IGNORECASE)


@dataclass
class ProductIntelligenceContext:
    entity: str
    raw_query: str
    expanded_terms: List[str]
    category: Optional[str] = None
    preferred_source: str = "db"


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.]+", "", str(value))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _coerce_int(value: Any) -> Optional[int]:
    numeric = _coerce_float(value)
    return int(numeric) if numeric is not None else None


def _coerce_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"false", "0", "no", "out_of_stock"}:
        return False
    if lowered in {"true", "1", "yes", "in_stock"}:
        return True
    return default


def _extract_unit(name: str, explicit_unit: Any) -> str:
    if explicit_unit:
        return str(explicit_unit).strip()
    match = _UNIT_PATTERN.search(name or "")
    return match.group(0) if match else ""


def _infer_platform(raw_platform: Any, url: Optional[str]) -> Platform:
    if raw_platform:
        mapped = data_layer._platform_value(str(raw_platform))
        if mapped:
            return mapped
    if url:
        hostname = urlparse(url).netloc.lower()
        for platform in Platform:
            if platform == Platform.external:
                continue
            if platform.value in hostname:
                return platform
    return Platform.external


def _stable_product_id(platform: Platform, name: str, url: Optional[str]) -> str:
    digest = hashlib.sha256(f"{platform.value}|{name}|{url or ''}".encode()).hexdigest()[:12]
    return f"{platform.value}-{digest}"


def map_external_product(
    item: Dict[str, Any],
    *,
    entity: str,
    default_source: str,
) -> Optional[PlatformProduct]:
    name = str(item.get("title") or item.get("name") or item.get("product_name") or "").strip()
    price = (
        _coerce_float(item.get("price"))
        or _coerce_float(item.get("current_price"))
        or _coerce_float(item.get("selling_price"))
    )
    if not name or price is None or price <= 0:
        return None
    url = item.get("product_url") or item.get("url") or item.get("link")
    platform = _infer_platform(item.get("platform"), url)
    product_id = str(item.get("product_id") or item.get("id") or item.get("sku") or "").strip()
    if not product_id:
        product_id = _stable_product_id(platform, name, url)
    normalized_name = str(item.get("normalized_name") or entity or name).strip().lower()
    original_price = _coerce_float(item.get("original_price") or item.get("mrp"))
    discount_percent = _coerce_float(item.get("discount_percent") or item.get("discount"))
    if discount_percent is None and original_price and original_price > price:
        discount_percent = round(((original_price - price) / original_price) * 100, 1)
    if original_price is None and discount_percent and discount_percent > 0:
        original_price = round(price / (1 - (discount_percent / 100)), 2)
    rating = _coerce_float(item.get("rating") or item.get("stars") or item.get("review_score"))
    return PlatformProduct(
        platform=platform,
        product_id=product_id,
        name=name,
        normalized_name=normalized_name,
        price=price,
        original_price=original_price,
        discount_percent=discount_percent,
        unit=_extract_unit(name, item.get("unit")),
        rating=rating,
        delivery_time_minutes=_coerce_int(item.get("delivery_time_minutes") or item.get("delivery_time")),
        in_stock=_coerce_bool(item.get("in_stock"), default=True),
        image_url=item.get("image_url") or item.get("image"),
        url=url,
        brand=item.get("brand") or data_layer._extract_brand(name),
        source=default_source,
    )


class ProductIntelligenceTool:
    tool_name = "base"

    def is_available(self, context: ProductIntelligenceContext) -> bool:
        return True

    def score(self, context: ProductIntelligenceContext) -> float:
        return 0.0

    async def fetch(self, context: ProductIntelligenceContext) -> List[Dict[str, Any]]:
        return []

    async def _get_cached(self, context: ProductIntelligenceContext) -> Optional[List[Dict[str, Any]]]:
        cache = get_cache()
        cache_key = f"{self.tool_name}|{context.entity}|{context.category or ''}"
        return await cache.get("product-intel", cache_key)

    async def _set_cached(self, context: ProductIntelligenceContext, rows: List[Dict[str, Any]]) -> None:
        cache = get_cache()
        cache_key = f"{self.tool_name}|{context.entity}|{context.category or ''}"
        await cache.set("product-intel", cache_key, {"rows": rows})


class ExternalApiTool(ProductIntelligenceTool):
    tool_name = "api"

    def __init__(self) -> None:
        self._settings = get_settings()

    def is_available(self, context: ProductIntelligenceContext) -> bool:
        return bool(self._settings.api_fallback_enabled and self._settings.external_product_api_url)

    def score(self, context: ProductIntelligenceContext) -> float:
        return 1.0 if self.is_available(context) else 0.0

    async def fetch(self, context: ProductIntelligenceContext) -> List[Dict[str, Any]]:
        cached = await self._get_cached(context)
        if cached:
            return cached.get("rows", [])
        retries = max(1, int(self._settings.api_fallback_max_retries))
        backoff = max(0.1, float(self._settings.api_fallback_backoff_seconds))
        async with httpx.AsyncClient(timeout=8.0) as client:
            for attempt in range(retries):
                try:
                    response = await client.get(
                        self._settings.external_product_api_url,
                        params={"q": context.entity},
                    )
                    if response.status_code == 429:
                        await asyncio.sleep(backoff * (2 ** attempt))
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    rows = payload.get("items", payload if isinstance(payload, list) else [])
                    normalized = [row for row in rows if isinstance(row, dict)]
                    await self._set_cached(context, normalized)
                    return normalized
                except Exception:
                    if attempt < retries - 1:
                        await asyncio.sleep(backoff * (2 ** attempt))
        return []


class HttpFetchTool(ProductIntelligenceTool):
    tool_name = "http"

    def __init__(self) -> None:
        self._settings = get_settings()

    def is_available(self, context: ProductIntelligenceContext) -> bool:
        return bool(self._settings.scraper_blinkit_url)

    def score(self, context: ProductIntelligenceContext) -> float:
        return 0.8 if self.is_available(context) else 0.0

    async def fetch(self, context: ProductIntelligenceContext) -> List[Dict[str, Any]]:
        cached = await self._get_cached(context)
        if cached:
            return cached.get("rows", [])
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    self._settings.scraper_blinkit_url,
                    params={"q": context.entity, "category": context.category or ""},
                )
                response.raise_for_status()
                rows = _extract_from_html(response.text)
                for row in rows:
                    row["source"] = "http_fetch"
                await self._set_cached(context, rows)
                return rows
            except Exception:
                logger.debug("HTTP fetch tool failed for %s", context.entity, exc_info=True)
                return []


class BlinkitScraperTool(ProductIntelligenceTool):
    tool_name = "scraper"

    def __init__(self) -> None:
        self._settings = get_settings()

    def is_available(self, context: ProductIntelligenceContext) -> bool:
        return bool(self._settings.scraper_enabled and self._settings.scraper_blinkit_url)

    def score(self, context: ProductIntelligenceContext) -> float:
        return 0.9 if self.is_available(context) else 0.0

    async def fetch(self, context: ProductIntelligenceContext) -> List[Dict[str, Any]]:
        cached = await self._get_cached(context)
        if cached:
            return cached.get("rows", [])
        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                response = await client.get(
                    self._settings.scraper_blinkit_url,
                    params={"category": context.category or context.entity},
                )
                response.raise_for_status()
                rows = _extract_from_html(response.text)
                for row in rows:
                    row["source"] = "scraper"
                await self._set_cached(context, rows)
                return rows
            except Exception:
                logger.debug("Scraper tool failed for %s", context.entity, exc_info=True)
                return []


class SearchFallbackTool(ProductIntelligenceTool):
    tool_name = "search"

    def score(self, context: ProductIntelligenceContext) -> float:
        return 0.6 if get_settings().mock_data_enabled else 0.3

    async def fetch(self, context: ProductIntelligenceContext) -> List[Dict[str, Any]]:
        rows = []
        seen = set()
        for key, products in data_layer._MOCK_PRODUCTS.items():
            key_score = max(
                SequenceMatcher(None, context.entity.lower(), key.lower()).ratio(),
                max((SequenceMatcher(None, term.lower(), key.lower()).ratio() for term in context.expanded_terms), default=0.0),
            )
            if context.category and data_layer._TERM_TO_CATEGORY.get(key) == context.category:
                key_score += 0.15
            token_overlap = any(
                set(data_layer._tokenize(term)).intersection(data_layer._tokenize(key))
                for term in context.expanded_terms
            )
            if key_score < 0.55 and not token_overlap:
                continue
            for item in products:
                dedupe_key = (item["platform"], item["product_id"])
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                row = dict(item)
                row["source"] = "search"
                rows.append(row)
        if rows:
            return rows

        category_entities = data_layer._CATEGORY_TO_ENTITIES.get(context.category or "", [])
        for key in category_entities or list(data_layer._MOCK_PRODUCTS.keys())[:3]:
            for item in data_layer._MOCK_PRODUCTS.get(key, [])[:2]:
                row = dict(item)
                row["source"] = "approximation"
                rows.append(row)
        return rows


class ProductIntelligenceRegistry:
    def __init__(self) -> None:
        self._tools: List[ProductIntelligenceTool] = [
            ExternalApiTool(),
            BlinkitScraperTool(),
            HttpFetchTool(),
            SearchFallbackTool(),
        ]

    def _available_tools(self, context: ProductIntelligenceContext) -> List[ProductIntelligenceTool]:
        tools = [tool for tool in self._tools if tool.is_available(context)]
        return sorted(tools, key=lambda tool: tool.score(context), reverse=True)

    async def fetch(self, context: ProductIntelligenceContext) -> Tuple[List[PlatformProduct], List[ToolAttempt]]:
        tools = self._available_tools(context)
        attempts: List[ToolAttempt] = []
        if not tools:
            return [], attempts

        primary_batch = tools[:2]
        secondary_batch = tools[2:]
        products = await self._run_batch(primary_batch, context, attempts)
        if products:
            return products, attempts
        for tool in secondary_batch:
            products = await self._run_batch([tool], context, attempts)
            if products:
                return products, attempts
        return [], attempts

    async def _run_batch(
        self,
        tools: List[ProductIntelligenceTool],
        context: ProductIntelligenceContext,
        attempts: List[ToolAttempt],
    ) -> List[PlatformProduct]:
        results = await asyncio.gather(*(tool.fetch(context) for tool in tools), return_exceptions=True)
        mapped: List[PlatformProduct] = []
        for tool, result in zip(tools, results):
            if isinstance(result, Exception):
                attempts.append(ToolAttempt(tool_name=tool.tool_name, success=False, error=str(result)))
                continue
            tool_products = [
                product
                for product in (
                    map_external_product(row, entity=context.entity, default_source=str(row.get("source") or tool.tool_name))
                    for row in result
                )
                if product is not None
            ]
            attempts.append(
                ToolAttempt(
                    tool_name=tool.tool_name,
                    success=bool(tool_products),
                    result_count=len(tool_products),
                )
            )
            mapped.extend(tool_products)
        return mapped

    async def approximate(self, context: ProductIntelligenceContext) -> List[PlatformProduct]:
        approximate = await SearchFallbackTool().fetch(context)
        products = [
            product
            for product in (
                map_external_product(row, entity=context.entity, default_source=str(row.get("source") or "approximation"))
                for row in approximate
            )
            if product is not None
        ]
        for product in products:
            if product.source == "search":
                product.source = "approximation"
        return products
