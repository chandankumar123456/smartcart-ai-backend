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
    cart_optimization = "cart_optimization"
    exploratory = "exploratory"
    unsupported = "unsupported"
    # Backward-compatible aliases used in older pipeline/tests (remove in v2.0).
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


class ItemAttributes(BaseModel):
    quantity: Optional[float] = None
    unit: Optional[str] = None
    preferences: List[str] = Field(default_factory=list)


class StructuredItem(BaseModel):
    name: str
    category: str = "general"
    attributes: ItemAttributes = Field(default_factory=ItemAttributes)


class QueryConstraints(BaseModel):
    budget: Optional[Dict[str, Any]] = None
    servings: Optional[int] = None
    preferences: List[str] = Field(default_factory=list)


class QueryMetadata(BaseModel):
    confidence: float = 0.0
    notes: str = ""


class CleanQuery(BaseModel):
    text: str
    language: str = "en"
    tokens: List[str] = Field(default_factory=list)
    normalized_text: str = ""


class IntentResult(BaseModel):
    intent: QueryIntent
    confidence: float = 0.0
    notes: str = ""
    secondary_intents: List[QueryIntent] = Field(default_factory=list)


class RawEntity(BaseModel):
    text: str
    entity_type: str = "product"
    confidence: float = 0.0


class RawEntities(BaseModel):
    entities: List[RawEntity] = Field(default_factory=list)
    primary_entity: Optional[str] = None
    ambiguity_flags: List[str] = Field(default_factory=list)
    candidate_entities: List[str] = Field(default_factory=list)


class NormalizedEntity(BaseModel):
    raw_text: str
    canonical_name: str
    category: Optional[str] = None
    possible_variants: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class NormalizedEntities(BaseModel):
    entities: List[NormalizedEntity] = Field(default_factory=list)
    unresolved_entities: List[str] = Field(default_factory=list)


class Constraints(BaseModel):
    budget: Optional[Dict[str, Any]] = None
    servings: Optional[int] = None
    preferences: List[str] = Field(default_factory=list)
    inferred_quantity_multiplier: float = 1.0
    ranking_preference_weights: Dict[str, float] = Field(default_factory=dict)
    conflict_notes: List[str] = Field(default_factory=list)


class DomainGuardResult(BaseModel):
    allowed: bool = True
    confidence: float = 1.0
    reason: str = ""


class FallbackDecision(BaseModel):
    used: bool = False
    mode: str = "none"
    reason: str = ""
    alternatives: List[str] = Field(default_factory=list)


class AmbiguityDecision(BaseModel):
    needs_resolution: bool = False
    resolution_strategy: str = "none"
    candidate_entities: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class ExecutionPlan(BaseModel):
    mode: str = "search_only"
    steps: List[str] = Field(default_factory=list)
    reason: str = ""


class StructuredQuery(BaseModel):
    """Output of QueryUnderstandingAgent."""

    product: str = Field(..., description="Primary product or entity extracted from query")
    filters: QueryFilters = Field(default_factory=QueryFilters)
    intent: QueryIntent = Field(default=QueryIntent.product_search)
    normalized_query: str = ""
    items: List[StructuredItem] = Field(default_factory=list)
    constraints: QueryConstraints = Field(default_factory=QueryConstraints)
    metadata: QueryMetadata = Field(default_factory=QueryMetadata)
    raw_query: str = Field(..., description="Original user query")


class NormalizedItem(BaseModel):
    """Normalized product intent used before matching."""

    canonical_name: str
    possible_variants: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    attributes: List[str] = Field(default_factory=list)


class FinalStructuredQuery(BaseModel):
    clean_query: CleanQuery
    intent_result: IntentResult
    raw_entities: RawEntities
    normalized_entities: NormalizedEntities
    constraints: Constraints
    domain_guard: DomainGuardResult
    ambiguity: AmbiguityDecision = Field(default_factory=AmbiguityDecision)
    fallback: FallbackDecision
    execution_plan: ExecutionPlan = Field(default_factory=ExecutionPlan)
    structured_query: StructuredQuery


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
    platforms: List[PlatformProduct] = Field(default_factory=list)


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
    ranked_list: List[RankedProduct] = Field(default_factory=list)
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

    deals: List[Deal] = Field(default_factory=list)
    trending_deals: List[Deal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Recipe Agent I/O
# ---------------------------------------------------------------------------


class Ingredient(BaseModel):
    name: str
    quantity: str
    unit: str


class IngredientProduct(BaseModel):
    ingredient: Ingredient
    matched_products: List[PlatformProduct] = Field(default_factory=list)
    cheapest_option: Optional[PlatformProduct] = None


class RecipeResult(BaseModel):
    """Output of RecipeAgent."""

    recipe_name: str
    servings: int = 2
    ingredients: List[IngredientProduct] = Field(default_factory=list)
    total_estimated_cost: float = 0.0
    missing_items: List[str] = Field(default_factory=list)


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

    original_items: List[CartItem] = Field(default_factory=list)
    platform_groups: List[CartPlatformGroup] = Field(default_factory=list)
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
    history: List[PricePoint] = Field(default_factory=list)
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    avg_price: Optional[float] = None


# ---------------------------------------------------------------------------
# Final API Response
# ---------------------------------------------------------------------------


class FinalResponse(BaseModel):
    """Standard response format for all AI endpoints."""

    query: str = ""
    results: List[Dict[str, Any]] = Field(default_factory=list)
    best_option: Dict[str, Any] = Field(default_factory=dict)
    deals: List[Dict[str, Any]] = Field(default_factory=list)
    total_price: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
