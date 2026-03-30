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

from app.core.exceptions import AgentException
from app.data.layer import match_products_for_entity
from app.data.models import PlatformProduct, QueryFilters, StructuredQuery, UnifiedProduct

logger = logging.getLogger(__name__)
TOP_K_FALLBACK = 3


class ProductMatchingAgent:
    """Fetches and normalises matching products from all platforms.

    SKU / entity matching is performed by the data layer. This agent applies
    post-fetch filtering based on the structured query filters.
    """

    async def run(self, structured_query: StructuredQuery) -> UnifiedProduct:
        entity = structured_query.product
        if not entity:
            raise AgentException("ProductMatchingAgent", "No product entity provided")

        products, match_meta = match_products_for_entity(entity)
        logger.debug(
            "[MATCHING] input_term=%s expanded_terms=%s matches_found=%s matched_products=%s",
            match_meta["input_term"],
            match_meta["expanded_terms"],
            len(match_meta["matched_keys"]),
            [p.name for p in products],
        )

        # Apply price filter
        filtered_products = self._apply_filters(products, structured_query.filters)

        fallback_triggered = False
        fallback_reason = ""
        if not filtered_products and products:
            fallback_triggered = True
            fallback_reason = "relax_filters_top_k"
            filtered_products = sorted(products, key=lambda p: p.price)[:TOP_K_FALLBACK]

        if match_meta["fallback_triggered"]:
            fallback_triggered = True
            fallback_reason = match_meta["fallback_reason"] or fallback_reason

        logger.debug(
            "[FALLBACK] triggered=%s reason=%s",
            fallback_triggered,
            fallback_reason,
        )

        return UnifiedProduct(
            entity=entity,
            normalized_name=entity.lower().strip(),
            platforms=filtered_products,
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
