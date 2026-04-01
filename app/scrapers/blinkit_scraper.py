"""Blinkit scraper pipeline (extract → clean → DB upsert)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup
import logging

from app.core.config import get_settings
from app.data.layer import save_products_to_db

_settings = get_settings()
logger = logging.getLogger(__name__)


def _extract_from_html(html: str) -> List[Dict[str, Any]]:
    """Best-effort extraction from Blinkit-like card markup."""
    soup = BeautifulSoup(html, "html.parser")
    rows: List[Dict[str, Any]] = []
    cards = soup.select("[data-product-id], .product-card, .ProductCard")
    for card in cards:
        product_id = (card.get("data-product-id") or "").strip()
        name_node = card.select_one("[data-name], .name, .product-name")
        price_node = card.select_one("[data-price], .price, .product-price")
        url_node = card.select_one("a[href]")
        if not product_id or not name_node or not price_node:
            continue
        name = name_node.get_text(" ", strip=True)
        price_text = price_node.get_text(" ", strip=True).replace("₹", "").replace(",", "").strip()
        try:
            price = float(price_text)
        except Exception:
            continue
        url = None
        if url_node is not None:
            raw = (url_node.get("href") or "").strip()
            if raw.startswith("http://") or raw.startswith("https://"):
                url = raw
        rows.append(
            {
                "platform": "blinkit",
                "product_id": product_id,
                "name": name,
                "normalized_name": name.lower().strip(),
                "brand": None,
                "category": None,
                "price": price,
                "product_url": url,
                "delivery_time": None,
                "rating": None,
                "source": "db",
                "last_updated": datetime.utcnow().isoformat(),
            }
        )
    return rows


def scrape_blinkit_products(category: str) -> List[Dict[str, Any]]:
    """
    Scrape Blinkit category listing when SCRAPER_BLINKIT_URL is configured.
    Returns cleaned rows ready for DB insert/upsert.
    """
    target_url = getattr(_settings, "scraper_blinkit_url", "")
    if not target_url:
        return []
    try:
        response = httpx.get(target_url, params={"category": category}, timeout=15.0)
        response.raise_for_status()
        return _extract_from_html(response.text)
    except Exception:
        logger.exception("Blinkit scrape failed for category=%s", category)
        return []


def run_blinkit_scrape(category: str) -> int:
    """Trigger scrape and store records in DB."""
    rows = scrape_blinkit_products(category)
    return save_products_to_db(rows)
