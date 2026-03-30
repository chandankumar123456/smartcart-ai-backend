# GAP_ANALYSIS

## 1. Gap Title
Generic Ingredient Matching Failure

## 2. Description
Generic ingredient queries like "chicken", "ghee", and "curd" were not reliably returning products across the search and recipe pipelines. This caused empty outputs and fallback-style responses despite relevant data being available.

## 3. Affected Modules
- QueryUnderstandingAgent
- ProductMatchingAgent
- Recipe Pipeline
- Cart Optimization Pipeline

## 4. Evidence
- input: "chicken"
- expanded_terms: ["chicken", "chicken breast", "chicken curry cut", "fresh chicken"]
- matches_found: > 0 after fix
- fallback_triggered: False for direct/expanded hits

- input: "dahi"
- expanded_terms include synonym mapping to "curd"
- matched_products: non-empty after fix

- input: "cheap ghee under 10"
- products_exist_for_entity: True
- filtered_matches_found: 0
- fallback_triggered: True
- fallback_reason: "relax_filters_top_k"
- returned_top_k: 3

## 5. Root Cause
The matching layer depended on strict entity alignment and only shallow fallback behavior. Query outputs and user inputs often use generic terms or aliases (for example, "dahi" vs "curd"), causing exact-key mismatch and empty result sets.

## 6. Fix Applied
- Query expansion for generic ingredients
  - chicken → chicken breast, chicken curry cut, fresh chicken
  - curd → dahi, yogurt, fresh curd
  - ghee → desi ghee, cow ghee
- Synonym mapping through alias normalization in data layer
- Fuzzy matching using token overlap and title-level partial checks
- Category fallback via term-to-category mapping when direct/fuzzy misses occur
- Top-K guarantee (relaxed-filter fallback) when filtered results are empty but products exist
- Structured debug logging for entry, parsing, matching, fallback, ranking/deals, and final output

## 7. Before vs After Behavior
Before:
- Generic ingredient terms could produce empty results
- recipe/cart paths could surface null/empty matching outputs
- limited traceability on where failure happened

After:
- Generic and alias terms return relevant products
- non-zero pricing for known ingredient searches
- fallback behavior is explicit, traceable, and logged
- reduced silent empty outputs due to top-k fallback guarantee

## 8. Validation
- "chicken" returns non-empty products in unit, pipeline, and API tests
- "dahi" maps to "curd" and returns products in unit, pipeline, and API tests
- strict filter case ("ghee under 10") still returns top-k fallback instead of empty
- Full test suite passes locally after changes

## 9. Status
FIXED
