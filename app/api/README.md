# api layer technical documentation

## endpoint inventory

routes are mounted in `app/main.py` by including `search`, `recipe`, `cart`, and `events` routers.

implemented endpoints:
- `POST /parse-query`
- `POST /search`
- `POST /execute`
- `POST /recipe`
- `POST /cart-optimization`
- `POST /platform-events`
- `GET /health`
- `GET /`
- `GET /ui` and static `/ui-assets/*`

## endpoint contracts

### post parse-query

handler: `app/api/routes/search.py::parse_query`

request model:
- `SearchRequest`
  - `query: str` (trimmed, min length 1, max 500)

response model:
- `FinalStructuredQuery`
  - includes `clean_query`, `intent_result`, `raw_entities`, `normalized_entities`, `constraints`, `domain_guard`, `ambiguity`, `fallback`, `execution_plan`, `execution_graph`, `candidate_paths`, `user_context`, `learning_signals`, `evaluation_history`, `failure_policies`, `platform_signals`, `coordination_trace`, `structured_query`

execution:
- verifies api key
- checks rate limit
- calls `pipeline.parse_query(body.query)`

### post search

handler: `app/api/routes/search.py::search`

request model:
- `FinalStructuredQuery`

response model:
- `FinalResponse`
  - `query: str`
  - `results: list[dict]`
  - `best_option: dict`
  - `deals: list[dict]`
  - `total_price: float`
  - `metadata: dict`

execution:
- verifies api key
- checks rate limit
- computes cache key from `body.structured_query.normalized_query` or `body.clean_query.normalized_text`
- returns cached response when present
- otherwise executes `pipeline.run_search(body)`
- stores result in cache namespace `search`

### post execute

handler: `app/api/routes/search.py::execute`

contract:
- request: `FinalStructuredQuery`
- response: `FinalResponse`
- implementation is direct alias to `search(...)`

### post recipe

handler: `app/api/routes/recipe.py::recipe`

request model:
- `RecipeRequest`
  - `query: str` (trimmed)
  - `servings: int` (`1..20`)

response model:
- `FinalResponse`

execution:
- api key + rate limit checks
- recipe cache lookup by `"{query}|servings={servings}"`
- on miss calls `pipeline.run_recipe(...)`

### post cart-optimization

handler: `app/api/routes/cart.py::cart_optimize`

request model:
- `CartOptimizeRequest`
  - `items: list[CartItem]` (must be non-empty)
  - item validation deduplicates by lowercased name and strips whitespace

response model:
- `FinalResponse`

execution:
- api key + rate limit checks
- calls `pipeline.run_cart_optimize(body.items)`

### post platform-events

handler: `app/api/routes/events.py::ingest_platform_event`

request model:
- `PlatformEvent`
  - `event_type: PlatformEventType`
  - `user_id: str` (default `anonymous`)
  - `payload: dict`
  - `timestamp: str`
  - `source: str` (default `api`)

response:
- plain `dict` returned by `PlatformEventIntelligence.ingest`

## execution rules

- `/search` and `/execute` accept `FinalStructuredQuery` only.
- raw user text is not accepted by `/search`.
- correct client sequence is:
  1. call `/parse-query`
  2. send returned contract to `/search` or `/execute`

## response structure details

search response rows are constructed in `ResponseBuilder.build_search_response` and include:
- `platform`
- `product_id`
- `name`
- `brand`
- `price`
- `original_price`
- `discount_percent`
- `unit`
- `rating`
- `delivery_time_minutes`
- `in_stock`
- `url`
- `link_status`
- `source`
- `score`
- `rank`

link status behavior:
- `available` when `url` is truthy
- `link unavailable` when `url` is null/empty

source behavior:
- forwarded from `PlatformProduct.source`
- expected values in runtime path are `db`, `api`, or `mock` depending on data-layer path

## validation and security

api key validation (`verify_api_key`):
- if `API_KEYS` is empty: open access
- if configured: missing/invalid key returns 401
- header name defaults to `X-API-Key` (configurable)

rate limit (`check_rate_limit`):
- sliding window in memory by client ip
- ip extraction prefers `X-Forwarded-For`, falls back to `request.client.host`
- exceeding limit returns 429

request validation:
- pydantic models enforce required fields and bounds
- whitespace-only query values are rejected by field validators

## error handling

global handlers are registered in `app/core/exceptions.py`:
- `SmartCartException` -> status from exception, structured error body
- generic `Exception` -> 500 with structured error body

## cache behavior

cache layer is optional:
- `CacheLayer.connect` tries redis and sets availability flag
- if redis is unavailable, api continues with cache no-op behavior
- `/health` reports cache state as `connected` or `unavailable`

## operational notes

startup lifecycle (`app/main.py`):
- initialize db schema (with degraded-mode continuation on failure)
- connect cache
- start queue workers
- start scraper scheduler

shutdown lifecycle:
- stop scheduler
- stop queue
- disconnect cache
- close db engine

## test command

```bash
python -m pytest -q tests/test_api.py
```
