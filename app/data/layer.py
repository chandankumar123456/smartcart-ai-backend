"""Data layer: provides product data from DB or mock store.

In production, this layer would fetch from a pre-processed database populated
by background scrapers. Real-time scraping is intentionally avoided in the
request path (see architecture principles).
"""

import random
from typing import Any, Dict, List, Optional, Tuple

from app.data.models import Platform, PlatformProduct, PriceHistory, PricePoint

# ---------------------------------------------------------------------------
# Mock product catalogue — simulates the structured database output
# ---------------------------------------------------------------------------

_MOCK_PRODUCTS: Dict[str, List[dict]] = {
    "milk": [
        {"platform": Platform.blinkit, "product_id": "bl-milk-001", "name": "Amul Taza Full Cream Milk 500ml", "normalized_name": "milk", "price": 30.0, "original_price": 30.0, "unit": "500ml", "rating": 4.5, "delivery_time_minutes": 12, "discount_percent": 0},
        {"platform": Platform.zepto, "product_id": "zp-milk-001", "name": "Amul Taza Toned Milk 500ml", "normalized_name": "milk", "price": 28.0, "original_price": 32.0, "unit": "500ml", "rating": 4.3, "delivery_time_minutes": 10, "discount_percent": 12.5},
        {"platform": Platform.instamart, "product_id": "im-milk-001", "name": "Nandini Full Cream Milk 500ml", "normalized_name": "milk", "price": 27.0, "original_price": 27.0, "unit": "500ml", "rating": 4.2, "delivery_time_minutes": 15, "discount_percent": 0},
        {"platform": Platform.bigbasket, "product_id": "bb-milk-001", "name": "Mother Dairy Full Cream Milk 500ml", "normalized_name": "milk", "price": 29.0, "original_price": 31.0, "unit": "500ml", "rating": 4.6, "delivery_time_minutes": 30, "discount_percent": 6.5},
        {"platform": Platform.jiomart, "product_id": "jm-milk-001", "name": "Amul Gold Full Cream Milk 500ml", "normalized_name": "milk", "price": 31.0, "original_price": 31.0, "unit": "500ml", "rating": 4.4, "delivery_time_minutes": 45, "discount_percent": 0},
        {"platform": Platform.dmart, "product_id": "dm-milk-001", "name": "DMart Fresh Toned Milk 500ml", "normalized_name": "milk", "price": 26.0, "original_price": 26.0, "unit": "500ml", "rating": 4.1, "delivery_time_minutes": 60, "discount_percent": 0},
    ],
    "bread": [
        {"platform": Platform.blinkit, "product_id": "bl-bread-001", "name": "Britannia Brown Bread 400g", "normalized_name": "bread", "price": 42.0, "original_price": 45.0, "unit": "400g", "rating": 4.3, "delivery_time_minutes": 12, "discount_percent": 6.7},
        {"platform": Platform.zepto, "product_id": "zp-bread-001", "name": "Modern Brown Bread 400g", "normalized_name": "bread", "price": 40.0, "original_price": 44.0, "unit": "400g", "rating": 4.2, "delivery_time_minutes": 10, "discount_percent": 9.1},
        {"platform": Platform.bigbasket, "product_id": "bb-bread-001", "name": "Harvest Gold White Bread 450g", "normalized_name": "bread", "price": 38.0, "original_price": 42.0, "unit": "450g", "rating": 4.4, "delivery_time_minutes": 30, "discount_percent": 9.5},
        {"platform": Platform.instamart, "product_id": "im-bread-001", "name": "Britannia White Bread 400g", "normalized_name": "bread", "price": 39.0, "original_price": 42.0, "unit": "400g", "rating": 4.1, "delivery_time_minutes": 15, "discount_percent": 7.1},
        {"platform": Platform.jiomart, "product_id": "jm-bread-001", "name": "Harvest Gold Brown Bread 400g", "normalized_name": "bread", "price": 41.0, "original_price": 41.0, "unit": "400g", "rating": 4.0, "delivery_time_minutes": 45, "discount_percent": 0},
        {"platform": Platform.dmart, "product_id": "dm-bread-001", "name": "English Oven Bread 400g", "normalized_name": "bread", "price": 36.0, "original_price": 38.0, "unit": "400g", "rating": 4.2, "delivery_time_minutes": 60, "discount_percent": 5.3},
    ],
    "eggs": [
        {"platform": Platform.blinkit, "product_id": "bl-eggs-001", "name": "Fresh Farm Eggs (6 pack)", "normalized_name": "eggs", "price": 54.0, "original_price": 60.0, "unit": "6 pcs", "rating": 4.4, "delivery_time_minutes": 12, "discount_percent": 10.0},
        {"platform": Platform.zepto, "product_id": "zp-eggs-001", "name": "Country Eggs (6 pack)", "normalized_name": "eggs", "price": 52.0, "original_price": 58.0, "unit": "6 pcs", "rating": 4.5, "delivery_time_minutes": 10, "discount_percent": 10.3},
        {"platform": Platform.instamart, "product_id": "im-eggs-001", "name": "Licious White Eggs (6 pack)", "normalized_name": "eggs", "price": 56.0, "original_price": 60.0, "unit": "6 pcs", "rating": 4.6, "delivery_time_minutes": 15, "discount_percent": 6.7},
        {"platform": Platform.bigbasket, "product_id": "bb-eggs-001", "name": "BB Farm Eggs (6 pack)", "normalized_name": "eggs", "price": 50.0, "original_price": 55.0, "unit": "6 pcs", "rating": 4.3, "delivery_time_minutes": 30, "discount_percent": 9.1},
        {"platform": Platform.jiomart, "product_id": "jm-eggs-001", "name": "Eggoz Nutrition Eggs (6 pack)", "normalized_name": "eggs", "price": 58.0, "original_price": 62.0, "unit": "6 pcs", "rating": 4.7, "delivery_time_minutes": 45, "discount_percent": 6.5},
    ],
    "rice": [
        {"platform": Platform.blinkit, "product_id": "bl-rice-001", "name": "India Gate Basmati Rice 1kg", "normalized_name": "rice", "price": 120.0, "original_price": 135.0, "unit": "1kg", "rating": 4.6, "delivery_time_minutes": 12, "discount_percent": 11.1},
        {"platform": Platform.zepto, "product_id": "zp-rice-001", "name": "Daawat Basmati Rice 1kg", "normalized_name": "rice", "price": 115.0, "original_price": 130.0, "unit": "1kg", "rating": 4.5, "delivery_time_minutes": 10, "discount_percent": 11.5},
        {"platform": Platform.bigbasket, "product_id": "bb-rice-001", "name": "Kohinoor Basmati Rice 1kg", "normalized_name": "rice", "price": 118.0, "original_price": 130.0, "unit": "1kg", "rating": 4.7, "delivery_time_minutes": 30, "discount_percent": 9.2},
        {"platform": Platform.instamart, "product_id": "im-rice-001", "name": "Fortune Basmati Rice 1kg", "normalized_name": "rice", "price": 122.0, "original_price": 135.0, "unit": "1kg", "rating": 4.4, "delivery_time_minutes": 15, "discount_percent": 9.6},
        {"platform": Platform.jiomart, "product_id": "jm-rice-001", "name": "India Gate Premium Basmati 1kg", "normalized_name": "rice", "price": 125.0, "original_price": 140.0, "unit": "1kg", "rating": 4.8, "delivery_time_minutes": 45, "discount_percent": 10.7},
        {"platform": Platform.dmart, "product_id": "dm-rice-001", "name": "D-Mart Basmati Rice 1kg", "normalized_name": "rice", "price": 110.0, "original_price": 120.0, "unit": "1kg", "rating": 4.3, "delivery_time_minutes": 60, "discount_percent": 8.3},
    ],
    "tomato": [
        {"platform": Platform.blinkit, "product_id": "bl-tomato-001", "name": "Fresh Tomatoes 500g", "normalized_name": "tomato", "price": 25.0, "original_price": 30.0, "unit": "500g", "rating": 4.2, "delivery_time_minutes": 12, "discount_percent": 16.7},
        {"platform": Platform.zepto, "product_id": "zp-tomato-001", "name": "Organic Tomatoes 500g", "normalized_name": "tomato", "price": 28.0, "original_price": 32.0, "unit": "500g", "rating": 4.4, "delivery_time_minutes": 10, "discount_percent": 12.5},
        {"platform": Platform.instamart, "product_id": "im-tomato-001", "name": "Fresh Red Tomatoes 500g", "normalized_name": "tomato", "price": 22.0, "original_price": 25.0, "unit": "500g", "rating": 4.1, "delivery_time_minutes": 15, "discount_percent": 12.0},
        {"platform": Platform.bigbasket, "product_id": "bb-tomato-001", "name": "BB Farm Tomatoes 500g", "normalized_name": "tomato", "price": 24.0, "original_price": 28.0, "unit": "500g", "rating": 4.3, "delivery_time_minutes": 30, "discount_percent": 14.3},
    ],
    "onion": [
        {"platform": Platform.blinkit, "product_id": "bl-onion-001", "name": "Fresh Onions 1kg", "normalized_name": "onion", "price": 35.0, "original_price": 40.0, "unit": "1kg", "rating": 4.1, "delivery_time_minutes": 12, "discount_percent": 12.5},
        {"platform": Platform.zepto, "product_id": "zp-onion-001", "name": "Red Onions 1kg", "normalized_name": "onion", "price": 32.0, "original_price": 38.0, "unit": "1kg", "rating": 4.2, "delivery_time_minutes": 10, "discount_percent": 15.8},
        {"platform": Platform.instamart, "product_id": "im-onion-001", "name": "Nashik Onions 1kg", "normalized_name": "onion", "price": 30.0, "original_price": 35.0, "unit": "1kg", "rating": 4.3, "delivery_time_minutes": 15, "discount_percent": 14.3},
        {"platform": Platform.bigbasket, "product_id": "bb-onion-001", "name": "BB Fresh Onions 1kg", "normalized_name": "onion", "price": 33.0, "original_price": 36.0, "unit": "1kg", "rating": 4.0, "delivery_time_minutes": 30, "discount_percent": 8.3},
    ],
    "oil": [
        {"platform": Platform.blinkit, "product_id": "bl-oil-001", "name": "Fortune Sunflower Oil 1L", "normalized_name": "oil", "price": 145.0, "original_price": 165.0, "unit": "1L", "rating": 4.5, "delivery_time_minutes": 12, "discount_percent": 12.1},
        {"platform": Platform.zepto, "product_id": "zp-oil-001", "name": "Saffola Gold Oil 1L", "normalized_name": "oil", "price": 155.0, "original_price": 175.0, "unit": "1L", "rating": 4.6, "delivery_time_minutes": 10, "discount_percent": 11.4},
        {"platform": Platform.bigbasket, "product_id": "bb-oil-001", "name": "Sundrop Sunflower Oil 1L", "normalized_name": "oil", "price": 140.0, "original_price": 160.0, "unit": "1L", "rating": 4.4, "delivery_time_minutes": 30, "discount_percent": 12.5},
        {"platform": Platform.dmart, "product_id": "dm-oil-001", "name": "DMart Sunflower Oil 1L", "normalized_name": "oil", "price": 135.0, "original_price": 150.0, "unit": "1L", "rating": 4.2, "delivery_time_minutes": 60, "discount_percent": 10.0},
    ],
    "butter": [
        {"platform": Platform.blinkit, "product_id": "bl-butter-001", "name": "Amul Butter 100g", "normalized_name": "butter", "price": 55.0, "original_price": 58.0, "unit": "100g", "rating": 4.7, "delivery_time_minutes": 12, "discount_percent": 5.2},
        {"platform": Platform.zepto, "product_id": "zp-butter-001", "name": "Amul Butter 100g", "normalized_name": "butter", "price": 53.0, "original_price": 58.0, "unit": "100g", "rating": 4.7, "delivery_time_minutes": 10, "discount_percent": 8.6},
        {"platform": Platform.bigbasket, "product_id": "bb-butter-001", "name": "Britannia Butter 100g", "normalized_name": "butter", "price": 52.0, "original_price": 56.0, "unit": "100g", "rating": 4.5, "delivery_time_minutes": 30, "discount_percent": 7.1},
    ],
    "pasta": [
        {"platform": Platform.blinkit, "product_id": "bl-pasta-001", "name": "Barilla Penne Pasta 500g", "normalized_name": "pasta", "price": 185.0, "original_price": 210.0, "unit": "500g", "rating": 4.5, "delivery_time_minutes": 12, "discount_percent": 11.9},
        {"platform": Platform.zepto, "product_id": "zp-pasta-001", "name": "Borges Penne Pasta 500g", "normalized_name": "pasta", "price": 175.0, "original_price": 200.0, "unit": "500g", "rating": 4.4, "delivery_time_minutes": 10, "discount_percent": 12.5},
        {"platform": Platform.bigbasket, "product_id": "bb-pasta-001", "name": "Del Monte Penne Pasta 500g", "normalized_name": "pasta", "price": 168.0, "original_price": 195.0, "unit": "500g", "rating": 4.6, "delivery_time_minutes": 30, "discount_percent": 13.8},
    ],
    "sugar": [
        {"platform": Platform.blinkit, "product_id": "bl-sugar-001", "name": "Tata Sugar 1kg", "normalized_name": "sugar", "price": 48.0, "original_price": 52.0, "unit": "1kg", "rating": 4.5, "delivery_time_minutes": 12, "discount_percent": 7.7},
        {"platform": Platform.zepto, "product_id": "zp-sugar-001", "name": "Madhur Sugar 1kg", "normalized_name": "sugar", "price": 45.0, "original_price": 50.0, "unit": "1kg", "rating": 4.3, "delivery_time_minutes": 10, "discount_percent": 10.0},
        {"platform": Platform.bigbasket, "product_id": "bb-sugar-001", "name": "BB Sugar 1kg", "normalized_name": "sugar", "price": 43.0, "original_price": 48.0, "unit": "1kg", "rating": 4.2, "delivery_time_minutes": 30, "discount_percent": 10.4},
        {"platform": Platform.dmart, "product_id": "dm-sugar-001", "name": "DMart Sugar 1kg", "normalized_name": "sugar", "price": 40.0, "original_price": 44.0, "unit": "1kg", "rating": 4.1, "delivery_time_minutes": 60, "discount_percent": 9.1},
    ],
    "curd": [
        {"platform": Platform.blinkit, "product_id": "bl-curd-001", "name": "Amul Masti Dahi 400g", "normalized_name": "curd", "price": 35.0, "original_price": 38.0, "unit": "400g", "rating": 4.4, "delivery_time_minutes": 12, "discount_percent": 7.9},
        {"platform": Platform.zepto, "product_id": "zp-curd-001", "name": "Mother Dairy Fresh Curd 400g", "normalized_name": "curd", "price": 32.0, "original_price": 35.0, "unit": "400g", "rating": 4.3, "delivery_time_minutes": 10, "discount_percent": 8.6},
        {"platform": Platform.bigbasket, "product_id": "bb-curd-001", "name": "Milky Mist Curd 400g", "normalized_name": "curd", "price": 34.0, "original_price": 36.0, "unit": "400g", "rating": 4.5, "delivery_time_minutes": 30, "discount_percent": 5.6},
    ],
    "ghee": [
        {"platform": Platform.blinkit, "product_id": "bl-ghee-001", "name": "Amul Pure Ghee 200ml", "normalized_name": "ghee", "price": 320.0, "original_price": 340.0, "unit": "200ml", "rating": 4.6, "delivery_time_minutes": 12, "discount_percent": 5.9},
        {"platform": Platform.zepto, "product_id": "zp-ghee-001", "name": "Patanjali Cow Ghee 200ml", "normalized_name": "ghee", "price": 280.0, "original_price": 305.0, "unit": "200ml", "rating": 4.3, "delivery_time_minutes": 10, "discount_percent": 8.2},
        {"platform": Platform.bigbasket, "product_id": "bb-ghee-001", "name": "Aashirvaad Svasti Ghee 200ml", "normalized_name": "ghee", "price": 295.0, "original_price": 315.0, "unit": "200ml", "rating": 4.4, "delivery_time_minutes": 30, "discount_percent": 6.3},
    ],
    "chicken": [
        {"platform": Platform.blinkit, "product_id": "bl-chicken-001", "name": "Fresh Chicken Curry Cut 500g", "normalized_name": "chicken", "price": 189.0, "original_price": 210.0, "unit": "500g", "rating": 4.2, "delivery_time_minutes": 12, "discount_percent": 10.0},
        {"platform": Platform.zepto, "product_id": "zp-chicken-001", "name": "Fresh Chicken Breast Boneless 500g", "normalized_name": "chicken", "price": 205.0, "original_price": 220.0, "unit": "500g", "rating": 4.4, "delivery_time_minutes": 10, "discount_percent": 6.8},
        {"platform": Platform.instamart, "product_id": "im-chicken-001", "name": "Broiler Fresh Chicken 500g", "normalized_name": "chicken", "price": 195.0, "original_price": 210.0, "unit": "500g", "rating": 4.3, "delivery_time_minutes": 15, "discount_percent": 7.1},
    ],
    "capsicum": [
        {"platform": Platform.blinkit, "product_id": "bl-capsicum-001", "name": "Fresh Green Capsicum 500g", "normalized_name": "capsicum", "price": 42.0, "original_price": 48.0, "unit": "500g", "rating": 4.1, "delivery_time_minutes": 12, "discount_percent": 12.5},
        {"platform": Platform.zepto, "product_id": "zp-capsicum-001", "name": "Shimla Mirch 500g", "normalized_name": "capsicum", "price": 40.0, "original_price": 45.0, "unit": "500g", "rating": 4.2, "delivery_time_minutes": 10, "discount_percent": 11.1},
    ],
    "paneer": [
        {"platform": Platform.blinkit, "product_id": "bl-paneer-001", "name": "Fresh Paneer Cubes 200g", "normalized_name": "paneer", "price": 95.0, "original_price": 105.0, "unit": "200g", "rating": 4.5, "delivery_time_minutes": 12, "discount_percent": 9.5},
        {"platform": Platform.bigbasket, "product_id": "bb-paneer-001", "name": "Malai Paneer 200g", "normalized_name": "paneer", "price": 90.0, "original_price": 100.0, "unit": "200g", "rating": 4.4, "delivery_time_minutes": 30, "discount_percent": 10.0},
    ],
    "wheat flour": [
        {"platform": Platform.blinkit, "product_id": "bl-atta-001", "name": "Aashirvaad Whole Wheat Atta 5kg", "normalized_name": "wheat flour", "price": 265.0, "original_price": 285.0, "unit": "5kg", "rating": 4.4, "delivery_time_minutes": 12, "discount_percent": 7.0},
        {"platform": Platform.dmart, "product_id": "dm-atta-001", "name": "DMart Wheat Flour Atta 5kg", "normalized_name": "wheat flour", "price": 240.0, "original_price": 260.0, "unit": "5kg", "rating": 4.2, "delivery_time_minutes": 60, "discount_percent": 7.7},
    ],
    "snacks": [
        {"platform": Platform.zepto, "product_id": "zp-snacks-001", "name": "Classic Salted Chips 100g", "normalized_name": "snacks", "price": 30.0, "original_price": 35.0, "unit": "100g", "rating": 4.0, "delivery_time_minutes": 10, "discount_percent": 14.3},
        {"platform": Platform.bigbasket, "product_id": "bb-snacks-001", "name": "Namkeen Mixture 200g", "normalized_name": "snacks", "price": 55.0, "original_price": 60.0, "unit": "200g", "rating": 4.1, "delivery_time_minutes": 30, "discount_percent": 8.3},
        {"platform": Platform.instamart, "product_id": "im-snacks-001", "name": "Marie Biscuits 250g", "normalized_name": "snacks", "price": 42.0, "original_price": 45.0, "unit": "250g", "rating": 4.2, "delivery_time_minutes": 15, "discount_percent": 6.7},
    ],
    "salad": [
        {"platform": Platform.zepto, "product_id": "zp-salad-001", "name": "Fresh Salad Leaves 200g", "normalized_name": "salad", "price": 65.0, "original_price": 70.0, "unit": "200g", "rating": 4.1, "delivery_time_minutes": 10, "discount_percent": 7.1},
        {"platform": Platform.blinkit, "product_id": "bl-salad-001", "name": "Lettuce Iceberg 1pc", "normalized_name": "salad", "price": 58.0, "original_price": 65.0, "unit": "1 pc", "rating": 4.0, "delivery_time_minutes": 12, "discount_percent": 10.8},
    ],
    "mayonnaise": [
        {"platform": Platform.blinkit, "product_id": "bl-mayo-001", "name": "Veeba Eggless Mayonnaise 250g", "normalized_name": "mayonnaise", "price": 109.0, "original_price": 119.0, "unit": "250g", "rating": 4.5, "delivery_time_minutes": 12, "discount_percent": 8.4},
        {"platform": Platform.zepto, "product_id": "zp-mayo-001", "name": "Del Monte Veg Mayonnaise 250g", "normalized_name": "mayonnaise", "price": 104.0, "original_price": 115.0, "unit": "250g", "rating": 4.4, "delivery_time_minutes": 10, "discount_percent": 9.6},
        {"platform": Platform.bigbasket, "product_id": "bb-mayo-001", "name": "Dr. Oetker FunFoods Mayonnaise 250g", "normalized_name": "mayonnaise", "price": 112.0, "original_price": 122.0, "unit": "250g", "rating": 4.6, "delivery_time_minutes": 30, "discount_percent": 8.2},
    ],
}

# Aliases: maps query terms to catalogue keys
_PRODUCT_ALIASES: Dict[str, str] = {
    "atta": "wheat flour",
    "wheat flour": "wheat flour",
    "toned milk": "milk",
    "full cream milk": "milk",
    "cow milk": "milk",
    "white bread": "bread",
    "brown bread": "bread",
    "chicken eggs": "eggs",
    "boiled eggs": "eggs",
    "basmati rice": "rice",
    "sunflower oil": "oil",
    "cooking oil": "oil",
    "vegetable oil": "oil",
    "salted butter": "butter",
    "white pasta": "pasta",
    "penne pasta": "pasta",
    "cane sugar": "sugar",
    "white sugar": "sugar",
    "dahi": "curd",
    "yoghurt": "curd",
    "yogurt": "curd",
    "fresh curd": "curd",
    "desi ghee": "ghee",
    "cow ghee": "ghee",
    "chicken breast": "chicken",
    "chicken curry cut": "chicken",
    "fresh chicken": "chicken",
    "shimla mirch": "capsicum",
    "green capsicum": "capsicum",
    "paneer cubes": "paneer",
    "fresh paneer": "paneer",
    "snack": "snacks",
    "salad leaves": "salad",
    "green leaves": "salad",
    "mayo": "mayonnaise",
    "mayonnaise": "mayonnaise",
    "veg mayo": "mayonnaise",
    "eggless mayo": "mayonnaise",
}

_QUERY_EXPANSIONS: Dict[str, List[str]] = {
    "chicken": ["chicken breast", "chicken curry cut", "fresh chicken"],
    "curd": ["dahi", "yogurt", "fresh curd"],
    "ghee": ["desi ghee", "cow ghee"],
    "capsicum": ["green capsicum", "shimla mirch"],
    "paneer": ["paneer cubes", "fresh paneer"],
    "snacks": ["chips", "biscuits", "namkeen"],
    "salad": ["salad leaves", "lettuce", "green leaves"],
    "wheat flour": ["atta", "whole wheat atta"],
    "mayonnaise": ["mayo", "veg mayo", "eggless mayo"],
}

_BRAND_TOKEN_BLACKLIST = {"fresh", "organic", "premium", "classic", "farm", "red", "green"}

_CATEGORY_TO_ENTITIES: Dict[str, List[str]] = {
    "dairy": ["milk", "curd", "butter", "ghee"],
    "poultry": ["chicken", "eggs"],
    "staples": ["rice", "sugar", "oil"],
    "vegetable": ["capsicum", "tomato", "onion", "salad"],
    "snacks": ["snacks", "bread", "butter"],
}

_TERM_TO_CATEGORY: Dict[str, str] = {
    "milk": "dairy",
    "curd": "dairy",
    "dahi": "dairy",
    "yogurt": "dairy",
    "yoghurt": "dairy",
    "ghee": "dairy",
    "chicken": "poultry",
    "capsicum": "vegetable",
    "paneer": "dairy",
    "atta": "staples",
    "wheat flour": "staples",
    "snacks": "snacks",
    "salad": "vegetable",
}


def _normalize(term: str) -> str:
    """Lowercase and strip a product term, apply aliases."""
    term = term.lower().strip()
    return _PRODUCT_ALIASES.get(term, term)


def _unique(items: List[str]) -> List[str]:
    """Return items without duplicates while preserving insertion order."""
    return list(dict.fromkeys([item for item in items if item]))


def _expand_query_terms(entity: str) -> List[str]:
    base = _normalize(entity)
    variants = [base] + _QUERY_EXPANSIONS.get(base, [])
    return _unique([_normalize(v) for v in variants])


def _tokenize(text: str) -> List[str]:
    return [t for t in text.lower().replace("-", " ").split() if t]


def _extract_brand(name: str) -> Optional[str]:
    tokens = [t for t in name.replace("-", " ").split() if t]
    if not tokens:
        return None
    for token in tokens[:3]:
        lower = token.lower()
        if lower in _BRAND_TOKEN_BLACKLIST:
            continue
        return token
    return tokens[0]


def _ensure_product_fields(item: dict) -> dict:
    enriched = dict(item)
    name = str(enriched.get("name") or "")
    enriched["brand"] = enriched.get("brand") or _extract_brand(name)
    enriched["source"] = str(enriched.get("source") or "db")
    return enriched


def _fallback_from_category(
    matched_keys: List[str],
    fallback_triggered: bool,
    fallback_reason: str,
    category_value: Optional[str],
) -> Tuple[List[str], bool, str]:
    if matched_keys or not category_value:
        return matched_keys, fallback_triggered, fallback_reason
    normalized = category_value.lower().strip()
    keys = _CATEGORY_TO_ENTITIES.get(normalized, [])
    if keys:
        return keys, True, f"category_fallback:{normalized}"
    return matched_keys, fallback_triggered, fallback_reason


def match_products_for_entity(
    entity: str,
    possible_variants: Optional[List[str]] = None,
    category: Optional[str] = None,
) -> Tuple[List[PlatformProduct], Dict[str, Any]]:
    """Return matched products and structured matching diagnostics.

    Returns:
        tuple[list[PlatformProduct], dict]:
            - products: merged product list for all matched catalogue keys.
            - metadata: debug details containing input term, expanded terms,
              matched catalogue keys, and fallback flags/reasons.

    Strategy:
        1) normalize + expand query term variants
        2) fuzzy token matching against catalogue keys and product titles
        3) category fallback when no direct/fuzzy key match is found
    """
    expanded_terms = _expand_query_terms(entity)
    if possible_variants:
        for variant in possible_variants:
            expanded_terms.extend(_expand_query_terms(variant))
    expanded_terms = _unique(expanded_terms)

    matched_keys: List[str] = []
    for key in _MOCK_PRODUCTS:
        key_tokens = set(_tokenize(key))
        for term in expanded_terms:
            term_tokens = set(_tokenize(term))
            if term == key:
                matched_keys.append(key)
                break
            if key_tokens.intersection(term_tokens):
                matched_keys.append(key)
                break
            if any(
                set(_tokenize(item["name"])).intersection(term_tokens)
                for item in _MOCK_PRODUCTS[key]
            ):
                matched_keys.append(key)
                break
    matched_keys = _unique(matched_keys)

    fallback_triggered = False
    fallback_reason = ""
    if not matched_keys:
        matched_keys, fallback_triggered, fallback_reason = _fallback_from_category(
            matched_keys, fallback_triggered, fallback_reason, category
        )
        for term in expanded_terms:
            inferred_category = _TERM_TO_CATEGORY.get(term)
            matched_keys, fallback_triggered, fallback_reason = _fallback_from_category(
                matched_keys, fallback_triggered, fallback_reason, inferred_category
            )
            if matched_keys:
                break

    raw: List[dict] = []
    seen_ids = set()
    for key in matched_keys:
        for item in _MOCK_PRODUCTS.get(key, []):
            dedupe_key = (item["platform"], item["product_id"])
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            raw.append(item)

    return (
        [PlatformProduct(**_ensure_product_fields(item)) for item in raw],
        {
            "input_term": entity,
            "expanded_terms": expanded_terms,
            "matched_keys": matched_keys,
            "fallback_triggered": fallback_triggered,
            "fallback_reason": fallback_reason,
        },
    )


def get_products_for_entity(entity: str) -> List[PlatformProduct]:
    """Return PlatformProduct list for a normalized entity name."""
    products, _ = match_products_for_entity(entity)
    return products


def get_price_history(entity: str, platform: Platform) -> PriceHistory:
    """Return mock price history for an entity on a platform."""
    key = _normalize(entity)
    raw = _MOCK_PRODUCTS.get(key, [])
    current_price = 50.0
    for item in raw:
        if item["platform"] == platform:
            current_price = item["price"]
            break

    # Simulate 7-day history with ±15% variation
    from datetime import date, timedelta

    history: List[PricePoint] = []
    for i in range(7, 0, -1):
        d = date.today() - timedelta(days=i)
        variation = current_price * random.uniform(-0.15, 0.15)
        price = round(current_price + variation, 2)
        history.append(PricePoint(date=str(d), price=price, platform=platform))

    prices = [p.price for p in history]
    return PriceHistory(
        entity=entity,
        platform=platform,
        history=history,
        min_price=min(prices),
        max_price=max(prices),
        avg_price=round(sum(prices) / len(prices), 2),
    )


def get_all_products() -> Dict[str, List[PlatformProduct]]:
    """Return entire mock catalogue as {entity: [products]}."""
    return {key: [PlatformProduct(**p) for p in items] for key, items in _MOCK_PRODUCTS.items()}
