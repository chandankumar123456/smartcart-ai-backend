"""Product Matching Agent.

Matches the same product across all supported platforms, handling naming differences
and normalising product data.

README
------
Ensures valid cross-platform comparison.
Input: StructuredQuery
Output: UnifiedProduct (list of PlatformProduct per platform)
"""

import logging
from typing import Any, Dict, Mapping

from app.agents.base_execution import BaseExecutionAgent
from app.core.exceptions import AgentException
import app.data.layer as data_layer
from app.agents.tools.product_intelligence import ProductIntelligenceContext, ProductIntelligenceRegistry
from app.data.models import MatchingDiagnostics, NormalizedItem, PlatformProduct, QueryFilters, StructuredQuery, ToolAttempt, UnifiedProduct

logger = logging.getLogger(__name__)
TOP_K_FALLBACK = 3
_MIN_HIGH_QUALITY_RESULTS = 2


class ProductMatchingAgent(BaseExecutionAgent):
    """Fetches and normalises matching products from all platforms.

    SKU / entity matching is performed by the data layer. This agent applies
    post-fetch filtering based on the structured query filters.
    """

    async def run(
        self,
        structured_query: StructuredQuery,
        normalized_item: NormalizedItem | None = None,
    ) -> UnifiedProduct:
        entity, expanded_terms, category, diagnostics, products, weak_match = self._initial_match(
            structured_query,
            normalized_item,
        )
        if not products or weak_match:
            tool_products, attempts = await self._tool_registry.fetch(
                self._build_tool_context(structured_query, entity, expanded_terms, category)
            )
            diagnostics.tool_attempts.extend(attempts)
            if tool_products:
                diagnostics.fallback_trace.append("tool_enrichment")
                diagnostics.matched_via = self._infer_primary_source(tool_products)
                diagnostics.approximate_match = any(product.source == "approximation" for product in tool_products)
                if diagnostics.approximate_match and "approximation" not in diagnostics.fallback_trace:
                    diagnostics.fallback_trace.append("approximation")
                products = self._dedupe_products(products + tool_products)
                self._update_source_breakdown(diagnostics, products)
        if not products:
            diagnostics.fallback_trace.append("approximation")
            approximate_products = await self._tool_registry.approximate(
                self._build_tool_context(
                    structured_query,
                    entity,
                    expanded_terms,
                    category or self._infer_category(expanded_terms),
                )
            )
            if approximate_products:
                diagnostics.approximate_match = True
                diagnostics.matched_via = "approximation"
                products = self._dedupe_products(approximate_products)
                diagnostics.matched_keys = data_layer._unique([p.normalized_name for p in products])
                self._update_source_breakdown(diagnostics, products)
        return self._build_unified_product(entity, structured_query.filters, diagnostics, products)

    def __init__(self) -> None:
        self._tool_registry = ProductIntelligenceRegistry()

    async def act(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        structured_query = state["structured_query"]
        normalized_item = state.get("normalized_item")
        if not normalized_item:
            raise AgentException("ProductMatchingAgent", "No normalized item provided")
        tool_result = state.get("tool_result")
        if tool_result:
            return self._consume_tool_result(state)

        entity, expanded_terms, category, diagnostics, products, weak_match = self._initial_match(
            structured_query,
            normalized_item,
        )
        if not products or weak_match:
            return {
                "current_step": "product_matching_node",
                "diagnostics": diagnostics,
                "preliminary_products": products,
                "tool_request": self._build_tool_request(
                    request_type="fetch",
                    structured_query=structured_query,
                    entity=entity,
                    expanded_terms=expanded_terms,
                    category=category,
                ),
                "tool_result": None,
                "last_observation": {
                    "phase": "db_match",
                    "result_count": len(products),
                    "weak_match": weak_match,
                },
            }
        return self._build_matching_update(
            state=state,
            entity=entity,
            diagnostics=diagnostics,
            products=products,
            filters=structured_query.filters,
        )

    async def execute_tool_request(self, tool_request: Dict[str, Any]) -> Dict[str, Any]:
        context = ProductIntelligenceContext(
            entity=tool_request["entity"],
            raw_query=tool_request["raw_query"],
            expanded_terms=list(tool_request.get("expanded_terms", [])),
            category=tool_request.get("category"),
        )
        request_type = tool_request.get("request_type", "fetch")
        if request_type == "approximate":
            products = await self._tool_registry.approximate(context)
            attempts = [
                ToolAttempt(
                    tool_name="approximation",
                    success=bool(products),
                    result_count=len(products),
                )
            ]
            return {
                "request_type": request_type,
                "entity": context.entity,
                "products": products,
                "attempts": attempts,
            }
        products, attempts = await self._tool_registry.fetch(context)
        return {
            "request_type": request_type,
            "entity": context.entity,
            "products": products,
            "attempts": attempts,
        }

    @staticmethod
    def _is_weak_match(entity: str, products: list[PlatformProduct]) -> bool:
        if not products:
            return True
        return ProductMatchingAgent._exact_hit_count(entity, products) == 0

    def _initial_match(
        self,
        structured_query: StructuredQuery,
        normalized_item: NormalizedItem | None,
    ) -> tuple[str, list[str], str | None, MatchingDiagnostics, list[PlatformProduct], bool]:
        entity = normalized_item.canonical_name if normalized_item else structured_query.product
        if not entity:
            raise AgentException("ProductMatchingAgent", "No product entity provided")
        variants = normalized_item.possible_variants if normalized_item else []
        category = normalized_item.category if normalized_item else None
        expanded_terms = data_layer._expand_query_terms(entity)
        for variant in variants:
            expanded_terms.extend(data_layer._expand_query_terms(variant))
        expanded_terms = data_layer._unique(expanded_terms)
        diagnostics = MatchingDiagnostics(
            input_term=entity,
            expanded_terms=expanded_terms,
            matched_via="db",
            fallback_trace=["db_lookup"],
        )
        products = data_layer._search_db_products(expanded_terms, category)
        diagnostics.matched_keys = data_layer._unique([p.normalized_name for p in products])
        self._update_source_breakdown(diagnostics, products)
        weak_match = self._is_weak_match(entity, products)
        if not products:
            diagnostics.fallback_trace.append("db_empty")
        elif weak_match:
            diagnostics.fallback_trace.append("db_low_coverage")
        return entity, expanded_terms, category, diagnostics, products, weak_match

    @staticmethod
    def _build_tool_context(
        structured_query: StructuredQuery,
        entity: str,
        expanded_terms: list[str],
        category: str | None,
    ) -> ProductIntelligenceContext:
        """Construct the context object consumed by product intelligence tools."""
        return ProductIntelligenceContext(
            entity=entity,
            raw_query=structured_query.raw_query,
            expanded_terms=expanded_terms,
            category=category,
        )

    def _build_tool_request(
        self,
        *,
        request_type: str,
        structured_query: StructuredQuery,
        entity: str,
        expanded_terms: list[str],
        category: str | None,
    ) -> Dict[str, Any]:
        return {
            "request_type": request_type,
            "entity": entity,
            "raw_query": structured_query.raw_query,
            "expanded_terms": expanded_terms,
            "category": category,
        }

    def _consume_tool_result(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        structured_query = state["structured_query"]
        normalized_item = state["normalized_item"]
        entity = normalized_item.canonical_name
        tool_result = dict(state.get("tool_result") or {})
        diagnostics = (state.get("diagnostics") or MatchingDiagnostics()).model_copy(deep=True)
        products = list(state.get("preliminary_products") or [])
        request_type = str(tool_result.get("request_type") or "fetch")
        tool_products = list(tool_result.get("products") or [])
        attempts = list(tool_result.get("attempts") or [])

        if request_type == "fetch":
            diagnostics.tool_attempts.extend(attempts)
            if tool_products:
                diagnostics.fallback_trace.append("tool_enrichment")
                diagnostics.matched_via = self._infer_primary_source(tool_products)
                diagnostics.approximate_match = any(product.source == "approximation" for product in tool_products)
                if diagnostics.approximate_match and "approximation" not in diagnostics.fallback_trace:
                    diagnostics.fallback_trace.append("approximation")
                products = self._dedupe_products(products + tool_products)
                self._update_source_breakdown(diagnostics, products)
                return self._build_matching_update(
                    state=state,
                    entity=entity,
                    diagnostics=diagnostics,
                    products=products,
                    filters=structured_query.filters,
                )
            if not products:
                return {
                    "current_step": "product_matching_node",
                    "tool_request": self._build_tool_request(
                        request_type="approximate",
                        structured_query=structured_query,
                        entity=entity,
                        expanded_terms=diagnostics.expanded_terms,
                        category=normalized_item.category or self._infer_category(diagnostics.expanded_terms),
                    ),
                    "tool_result": None,
                    "last_observation": {
                        "phase": "tool_fetch_empty",
                        "result_count": 0,
                    },
                }
            diagnostics.fallback_trace.append("tool_fetch_empty")
            return self._build_matching_update(
                state=state,
                entity=entity,
                diagnostics=diagnostics,
                products=products,
                filters=structured_query.filters,
            )

        diagnostics.tool_attempts.extend(attempts)
        if tool_products:
            diagnostics.fallback_trace.append("approximation")
            diagnostics.approximate_match = True
            diagnostics.matched_via = "approximation"
            products = self._dedupe_products(tool_products)
            diagnostics.matched_keys = data_layer._unique([p.normalized_name for p in products])
            self._update_source_breakdown(diagnostics, products)
        return self._build_matching_update(
            state=state,
            entity=entity,
            diagnostics=diagnostics,
            products=products,
            filters=structured_query.filters,
        )

    def _build_matching_update(
        self,
        *,
        state: Mapping[str, Any],
        entity: str,
        diagnostics: MatchingDiagnostics,
        products: list[PlatformProduct],
        filters: QueryFilters,
    ) -> Dict[str, Any]:
        unified_product = self._build_unified_product(entity, filters, diagnostics, products)
        path_history = list(state.get("path_history", []))
        path_history.append(
            {
                "path_id": state.get("selected_path", "path-0"),
                "entity": state.get("current_entity", entity),
                "result_count": len(unified_product.platforms),
                "quality_score": unified_product.diagnostics.quality_score,
                "matched_via": unified_product.diagnostics.matched_via,
            }
        )
        return {
            "current_step": "product_matching_node",
            "unified_product": unified_product,
            "diagnostics": unified_product.diagnostics,
            "tool_trace": [attempt.model_dump() for attempt in unified_product.diagnostics.tool_attempts],
            "tool_attempts": unified_product.diagnostics.tool_attempts,
            "path_history": path_history,
            "tool_request": None,
            "tool_result": None,
            "preliminary_products": [],
            "last_observation": {
                "phase": "matching_complete",
                "result_count": len(unified_product.platforms),
                "quality_score": unified_product.diagnostics.quality_score,
            },
        }

    def _build_unified_product(
        self,
        entity: str,
        filters: QueryFilters,
        diagnostics: MatchingDiagnostics,
        products: list[PlatformProduct],
    ) -> UnifiedProduct:
        logger.debug(
            "[MATCHING] input_term=%s expanded_terms=%s matches_found=%s matched_products=%s",
            diagnostics.input_term,
            diagnostics.expanded_terms,
            len(diagnostics.matched_keys),
            [p.name for p in products],
        )
        filtered_products = self._apply_filters(products, filters)
        fallback_triggered = False
        fallback_reason = ""
        if not filtered_products and products:
            fallback_triggered = True
            fallback_reason = "relax_filters_top_k"
            filtered_products = sorted(products, key=lambda p: p.price)[:TOP_K_FALLBACK]
            diagnostics.fallback_trace.append(fallback_reason)
        elif not filtered_products:
            diagnostics.fallback_trace.append("no_usable_products")
        logger.debug(
            "[FALLBACK] triggered=%s reason=%s",
            fallback_triggered,
            fallback_reason,
        )
        diagnostics.quality_score = self._compute_quality_score(entity, filtered_products or products, diagnostics)
        return UnifiedProduct(
            entity=entity,
            normalized_name=entity.lower().strip(),
            platforms=filtered_products,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _dedupe_products(products: list[PlatformProduct]) -> list[PlatformProduct]:
        deduped: list[PlatformProduct] = []
        seen = set()
        for product in products:
            key = (
                product.platform.value,
                product.product_id or "",
                product.url or "",
                product.normalized_name,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(product)
        return deduped

    @staticmethod
    def _infer_primary_source(products: list[PlatformProduct]) -> str:
        if not products:
            return "db"
        counts: dict[str, int] = {}
        for product in products:
            counts[product.source] = counts.get(product.source, 0) + 1
        return max(counts, key=counts.get)

    @staticmethod
    def _update_source_breakdown(diagnostics: MatchingDiagnostics, products: list[PlatformProduct]) -> None:
        counts: dict[str, int] = {}
        for product in products:
            counts[product.source] = counts.get(product.source, 0) + 1
        diagnostics.source_breakdown = counts

    @staticmethod
    def _infer_category(expanded_terms: list[str]) -> str | None:
        for term in expanded_terms:
            category = data_layer._TERM_TO_CATEGORY.get(term)
            if category:
                return category
        return None

    @staticmethod
    def _compute_quality_score(
        entity: str,
        products: list[PlatformProduct],
        diagnostics: MatchingDiagnostics,
    ) -> float:
        """Score matching quality as source bonus + coverage + exactness - approximation penalty."""
        if not products:
            return 0.0
        exact_hits = ProductMatchingAgent._exact_hit_count(entity, products)
        source_bonus = 0.15 if diagnostics.matched_via == "db" else 0.1
        approximate_penalty = 0.25 if diagnostics.approximate_match else 0.0
        coverage_score = min(0.5, len(products) * 0.1)
        exact_score = min(0.4, exact_hits * 0.2)
        return max(0.0, min(1.0, round(source_bonus + coverage_score + exact_score - approximate_penalty, 4)))

    @staticmethod
    def _exact_hit_count(entity: str, products: list[PlatformProduct]) -> int:
        normalized_entity = entity.lower().strip()
        return sum(
            1 for p in products
            if p.normalized_name == normalized_entity or normalized_entity in p.name.lower()
        )

    @staticmethod
    def _apply_filters(
        products: list[PlatformProduct], filters: QueryFilters
    ) -> list[PlatformProduct]:
        result = []
        for p in products:
            if filters.max_price is not None and p.price > filters.max_price:
                continue
            if filters.min_price is not None and p.price < filters.min_price:
                continue
            if filters.brand is not None:
                if filters.brand.lower() not in p.name.lower():
                    continue
            result.append(p)
        return result
