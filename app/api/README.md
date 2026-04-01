# FastAPI Backend Documentation

This document covers the technical backend API layer for SmartCart AI.

---

## 1) Purpose

The FastAPI backend is the execution layer connecting:

```text
Client → API Layer → Security/Validation → Orchestrator → Agents/Data → Response JSON
```

It is responsible for:

- request validation and normalization
- orchestration entry-point invocation
- cache usage
- secure access and rate limiting
- consistent JSON responses and error handling

Architecture contract:
- Request-time search is **database-first** through the structured data layer.
- Scrapers/cleaners/queue refresh data in background.
- External APIs are fallback/enrichment only.

---

## 2) API Module Structure

```text
app/api/
  request_handler.py      # request schemas + validators
  routes/
    search.py             # /parse-query, /search, /execute
    recipe.py             # /recipe
    cart.py               # /cart-optimization
```

Application bootstrap is in `app/main.py`.

---

## 3) Exposed Endpoints

## 3.1 `POST /parse-query`

### Purpose
Intelligence-layer endpoint that converts raw natural language into `FinalStructuredQuery`.

### Flow
1. Validate payload (`SearchRequest`)
2. Security + rate limit checks
3. Run `AgentPipeline.parse_query`
4. Return strict machine-readable intelligence contract

---

## 3.2 `POST /search`

### Purpose
Primary execution endpoint for structured intelligence.

### Flow
1. Validate payload (`FinalStructuredQuery`)
2. Security + rate limit checks
3. Cache lookup
4. Run graph-based execution with candidate path branching
5. Evaluation-governed selection/retry loop
6. Cache write-through
7. Return `FinalResponse`

Result payload fields include:
- name, brand, price
- platform/store
- delivery estimate (if available)
- store redirection URL or explicit `link unavailable` status
- source marker (`db` / `api`)

---

## 3.3 `POST /execute`

### Purpose
Strict alias of `/search` with identical contract (`FinalStructuredQuery` only).

---

## 3.4 `POST /recipe`

### Purpose
Recipe planning to grocery mapping endpoint.

### Flow
1. Validate payload (`RecipeRequest`)
2. Security + rate limit checks
3. Cache lookup with query+servings key
4. Run `AgentPipeline.run_recipe`
5. Cache write-through
6. Return `FinalResponse`

---

## 3.5 `POST /cart-optimization`

### Purpose
Optimizes a list of items into lowest-cost split-order strategy.

### Flow
1. Validate payload (`CartOptimizeRequest`)
2. Security + rate limit checks
3. Run `AgentPipeline.run_cart_optimize`
4. Return `FinalResponse`

---

## 4) Non-AI Support Endpoints

- `GET /` — basic service metadata
- `GET /health` — service health and cache availability

---

## 5) Request Validation

Defined in `app/api/request_handler.py`.

### Schemas
- `SearchRequest`
- `RecipeRequest`
- `CartOptimizeRequest`

### Validation rules
- query must be non-empty after trimming
- servings range: 1–20
- cart items list must be non-empty
- duplicate cart items are normalized

---

## 6) Security Layer Integration

Defined in `app/core/security.py`.

### Authentication
- API key via `X-API-Key` header
- open mode allowed if no keys configured (development convenience)

### Rate limiting
- Sliding window in-memory limiter
- Proxy-aware client IP extraction using `X-Forwarded-For` fallback to client host
- Returns HTTP `429` on overflow (client should retry with backoff)

---

## 7) Error Handling

Defined in `app/core/exceptions.py` and registered in `app/main.py`.

### Behavior
- Custom exceptions mapped to structured JSON errors
- Generic exception fallback to stable JSON error payload
- Ensures clients always receive parseable JSON responses

---

## 8) Caching Strategy

Defined in `app/cache/redis_cache.py`.

- Deterministic hashed cache keys
- Search and recipe endpoints are cache-enabled
- Graceful fallback when Redis is unavailable
- Core API behavior must remain correct with cache disabled

---

## 9) Orchestrator Binding

Routes call orchestrator methods:

- `parse_query(query)`
- `run_search(final_structured_query)`
- `run_recipe(query, servings)`
- `run_cart_optimize(items)`

Orchestrator implementation: `app/orchestrator/pipeline.py`.

---

## 10) Response Contract

All routes return `FinalResponse` from `app/data/models.py`:

```json
{
  "query": "",
  "results": [],
  "best_option": {},
  "deals": [],
  "total_price": 0
}
```

Current implementation includes additional `metadata`.

Product result records include `brand`, `source`, and `link_status` to support transparent DB/API provenance and redirect availability.

---

## 11) Runtime Configuration

Configuration source:

- `.env` (see `.env.example`)
- `app/core/config.py`

Important backend settings:

- `API_KEYS`
- `RATE_LIMIT_REQUESTS`
- `RATE_LIMIT_WINDOW_SECONDS`
- `REDIS_URL`
- `CACHE_TTL_SECONDS`
- `LLM_PROVIDER`

---

## 12) How to Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open docs:

- Swagger UI: `/docs`
- ReDoc: `/redoc`

---

## 13) Backend Tests

Relevant test files:

- `tests/test_api.py` — route-level tests
- `tests/test_pipeline.py` — orchestrator-backed behavior

These tests validate request validation, response shape, and route outcomes.


## 14) Structured-only execution guarantees

`/search` and `/execute` consume only `FinalStructuredQuery`.
The contract includes `execution_graph`, `candidate_paths`, `learning_signals`, `evaluation_history`, and `failure_policies`, enabling adaptive execution without raw query leakage to execution agents.

Ambiguity handling is intentionally conservative: single high-confidence entities do not trigger unnecessary ambiguity resolution.


## Platform event intelligence endpoint

### POST /platform-events
Ingests real-time platform events into the AI intelligence layer.

Accepted event types:
- `user.behavior`
- `order.created`
- `inventory.updated`
- `price.updated`

Effects on execution:
- updates shared memory and user model
- influences parse/query planning via `platform_signals`
- influences execution via live inventory/price adaptation
- enriches response metadata with coordination and predictive context

Structured query integration now includes `platform_signals` and `coordination_trace` fields in `FinalStructuredQuery`.
