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

---

## 2) API Module Structure

```text
app/api/
  request_handler.py      # request schemas + validators
  routes/
    search.py             # /ai/search
    recipe.py             # /ai/recipe
    cart.py               # /ai/cart-optimize
```

Application bootstrap is in `app/main.py`.

---

## 3) Exposed Endpoints

Base prefix: `/ai`

## 3.1 `POST /ai/search`

### Purpose
Primary product discovery and cross-platform comparison endpoint.

### Flow
1. Validate payload (`SearchRequest`)
2. Security + rate limit checks
3. Cache lookup
4. Run `AgentPipeline.run_search`
5. Cache write-through
6. Return `FinalResponse`

---

## 3.2 `POST /ai/recipe`

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

## 3.3 `POST /ai/cart-optimize`

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

---

## 9) Orchestrator Binding

Routes call orchestrator methods:

- `run_search(query)`
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

