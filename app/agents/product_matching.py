"""Product Matching Agent.

Matches the same product across all supported platforms, handling naming differences
and normalising product data.

README
------
Ensures valid cross-platform comparison.
Input: StructuredQuery
Output: UnifiedProduct (list of PlatformProduct per platform)
"""

from app.core.exceptions import AgentException
from app.data.layer import get_products_for_entity
from app.data.models import PlatformProduct, QueryFilters, StructuredQuery, UnifiedProduct


class ProductMatchingAgent:
    """Fetches and normalises matching products from all platforms.

    SKU / entity matching is performed by the data layer. This agent applies
    post-fetch filtering based on the structured query filters.
    """

    async def run(self, structured_query: StructuredQuery) -> UnifiedProduct:
        entity = structured_query.product
        if not entity:
            raise AgentException("ProductMatchingAgent", "No product entity provided")

        products = get_products_for_entity(entity)

        # Apply price filter
        products = self._apply_filters(products, structured_query.filters)

        return UnifiedProduct(
            entity=entity,
            normalized_name=entity.lower().strip(),
            platforms=products,
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
