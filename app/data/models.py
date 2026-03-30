"""Pydantic data models shared across agents, API, and response layers."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Intent
# ---------------------------------------------------------------------------


class QueryIntent(str, Enum):
    product_search = "product_search"
    recipe = "recipe"
    deal_search = "deal_search"
    cart_optimize = "cart_optimize"


# ---------------------------------------------------------------------------
# Query Understanding Agent I/O
# ---------------------------------------------------------------------------


class QueryFilters(BaseModel):
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    category: Optional[str] = None
    quantity: Optional[str] = None
    brand: Optional[str] = None


class StructuredQuery(BaseModel):
    """Output of QueryUnderstandingAgent."""

    product: str = Field(..., description="Primary product or entity extracted from query")
    filters: QueryFilters = Field(default_factory=QueryFilters)
    intent: QueryIntent = Field(default=QueryIntent.product_search)
    raw_query: str = Field(..., description="Original user query")


class NormalizedItem(BaseModel):
    """Normalized product intent used before matching."""

    canonical_name: str
    possible_variants: List[str] = []
    category: Optional[str] = None
    attributes: List[str] = []


# ---------------------------------------------------------------------------
# Product / Platform
# ---------------------------------------------------------------------------


class Platform(str, Enum):
    blinkit = "blinkit"
    zepto = "zepto"
    instamart = "instamart"
    bigbasket = "bigbasket"
    jiomart = "jiomart"
    dmart = "dmart"


class PlatformProduct(BaseModel):
    platform: Platform
    product_id: str
    name: str
    normalized_name: str
    price: float
    original_price: Optional[float] = None
    discount_percent: Optional[float] = None
    unit: str = ""
    rating: Optional[float] = None
    delivery_time_minutes: Optional[int] = None
    in_stock: bool = True
    image_url: Optional[str] = None
    url: Optional[str] = None


class UnifiedProduct(BaseModel):
    """Output of ProductMatchingAgent — same product across platforms."""

    entity: str
    normalized_name: str = ""
    platforms: List[PlatformProduct] = []


# ---------------------------------------------------------------------------
# Ranking Agent I/O
# ---------------------------------------------------------------------------


class RankedProduct(BaseModel):
    platform: Platform
    product: PlatformProduct
    score: float = Field(..., description="Composite ranking score (higher = better)")
    rank: int


class RankingResult(BaseModel):
    """Output of RankingAgent."""

    entity: str
    ranked_list: List[RankedProduct] = []
    best_option: Optional[RankedProduct] = None


# ---------------------------------------------------------------------------
# Deal Detection Agent I/O
# ---------------------------------------------------------------------------


class Deal(BaseModel):
    platform: Platform
    product_name: str
    original_price: float
    current_price: float
    discount_percent: float
    deal_type: str  # "discount", "price_drop", "trending"
    label: str


class DealResult(BaseModel):
    """Output of DealDetectionAgent."""

    deals: List[Deal] = []
    trending_deals: List[Deal] = []


# ---------------------------------------------------------------------------
# Recipe Agent I/O
# ---------------------------------------------------------------------------


class Ingredient(BaseModel):
    name: str
    quantity: str
    unit: str


class IngredientProduct(BaseModel):
    ingredient: Ingredient
    matched_products: List[PlatformProduct] = []
    cheapest_option: Optional[PlatformProduct] = None


class RecipeResult(BaseModel):
    """Output of RecipeAgent."""

    recipe_name: str
    servings: int = 2
    ingredients: List[IngredientProduct] = []
    total_estimated_cost: float = 0.0
    missing_items: List[str] = []


# ---------------------------------------------------------------------------
# Cart Optimization
# ---------------------------------------------------------------------------


class CartItem(BaseModel):
    name: str
    quantity: int = 1


class CartPlatformGroup(BaseModel):
    platform: Platform
    items: List[PlatformProduct] = []
    subtotal: float = 0.0


class CartOptimizationResult(BaseModel):
    """Result of cart split optimization."""

    original_items: List[CartItem] = []
    platform_groups: List[CartPlatformGroup] = []
    total_optimized_cost: float = 0.0
    savings: float = 0.0


# ---------------------------------------------------------------------------
# Price History
# ---------------------------------------------------------------------------


class PricePoint(BaseModel):
    date: str
    price: float
    platform: Platform


class PriceHistory(BaseModel):
    entity: str
    platform: Platform
    history: List[PricePoint] = []
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    avg_price: Optional[float] = None


# ---------------------------------------------------------------------------
# Final API Response
# ---------------------------------------------------------------------------


class FinalResponse(BaseModel):
    """Standard response format for all AI endpoints."""

    query: str = ""
    results: List[Dict[str, Any]] = []
    best_option: Dict[str, Any] = {}
    deals: List[Dict[str, Any]] = []
    total_price: float = 0.0
    metadata: Dict[str, Any] = {}
