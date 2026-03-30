# SmartCart AI Backend

SmartCart AI Backend is a **multi-agent grocery intelligence system** built with FastAPI.  
It converts natural-language grocery queries into structured decisions: price comparison, best option ranking, deal detection, recipe-to-cart mapping, and cart cost optimization across multiple platforms.

---

## 1) Project Scope

This backend implements:

- **AI Logic (Multi-Agent System)**  
  Query understanding, product matching, ranking, deal detection, recipe planning, cart optimization.
- **AI Backend (FastAPI + Orchestration)**  
  API endpoints, orchestration, LLM management, cache layer, queue workers, security layer, and standardized JSON responses.

Out of scope for this repository:

- Frontend applications
- Non-AI backend features outside orchestration/data access

---

## 2) High-Level Architecture

```text
User
  → FastAPI API Layer
  → Request Validation + Security
  → Orchestrator (AgentPipeline)
  → AI Agents + Data Layer
  → Ranking / Deals / Optimization
  → Response Builder
  → Structured JSON Response
```

Production-oriented flow:

```text
User → CDN → Load Balancer → FastAPI Backend → AI System → Database/Cache
```

---

## 3) Core Components

### 3.1 API / Backend Layer

- **FastAPI app**: `app/main.py`
- **Routes**: `app/api/routes/`
  - `search.py`
  - `recipe.py`
  - `cart.py`
- **Request validation**: `app/api/request_handler.py`
- **Response assembly**: `app/response/builder.py`
- **Global exception handling**: `app/core/exceptions.py`

### 3.2 AI Orchestration Layer

- **Orchestrator**: `app/orchestrator/pipeline.py`
  - Executes multi-agent pipeline
  - Supports intent-based branch to recipe pipeline
  - Handles cart optimization workflow

### 3.3 AI Agent Layer

- `app/agents/query_understanding.py`
- `app/agents/product_matching.py`
- `app/agents/ranking.py`
- `app/agents/deal_detection.py`
- `app/agents/recipe.py`

### 3.4 LLM Layer

- **LLM Manager**: `app/llm/manager.py`
  - OpenAI + Groq support
  - Structured JSON enforcement
  - Provider fallback handling

### 3.5 Data / Performance / Reliability

- **Data models**: `app/data/models.py`
- **Data access layer**: `app/data/layer.py` (pre-processed/mock catalog)
- **Redis cache**: `app/cache/redis_cache.py`
- **Queue workers**: `app/queue/worker.py`

### 3.6 Security

- **API key auth**
- **Proxy-aware IP rate limiting**
- Security module: `app/core/security.py`

---

## 4) Multi-Agent Pipeline

### Standard Search Pipeline

```text
User Query
  → QueryUnderstandingAgent
  → ProductMatchingAgent
  → RankingAgent
  → DealDetectionAgent
  → ResponseBuilder
```

### Recipe Pipeline

```text
User Recipe Query
  → QueryUnderstandingAgent (intent=recipe)
  → RecipeAgent
  → Ingredient-product mapping
  → Cheapest-option selection
  → ResponseBuilder
```

### Cart Optimization Pipeline

```text
Cart Items
  → Product lookup across platforms
  → Cheapest item-level pick
  → Platform grouping
  → Savings estimation
  → ResponseBuilder
```

---

## 5) Supported Platforms

Current platform model supports:

- Blinkit
- Zepto
- Instamart
- BigBasket
- JioMart
- DMart

---

## 6) API Reference

Base path: `/ai`

### `POST /ai/search`
Primary query endpoint for grocery search and comparison.

Request:

```json
{
  "query": "cheap milk under 35"
}
```

### `POST /ai/recipe`
Converts recipe intent into ingredient list + mapped products.

Request:

```json
{
  "query": "tomato pasta",
  "servings": 2
}
```

### `POST /ai/cart-optimize`
Optimizes total cart cost with split-order strategy.

Request:

```json
{
  "items": [
    { "name": "milk", "quantity": 1 },
    { "name": "bread", "quantity": 1 }
  ]
}
```

### Health and metadata endpoints

- `GET /` → basic service info + endpoint list
- `GET /health` → app status and cache status

---

## 7) Standard Response Contract

All AI endpoints return structured JSON based on:

```json
{
  "query": "",
  "results": [],
  "best_option": {},
  "deals": [],
  "total_price": 0
}
```

Current implementation also includes `metadata` for debugging/observability.

---

## 8) Configuration

Environment configuration lives in `.env` (see `.env.example`):

- App: `DEBUG`
- Security: `API_KEYS`, rate limit settings
- LLM: provider and model keys/settings
- Redis: URL + TTL
- Data mode: mock/preprocessed switch

Core settings class: `app/core/config.py`.

---

## 9) Caching & Queue Design

### Redis Cache

- Cache keys are deterministic and hashed
- Read-through pattern used in search and recipe flows
- Graceful degradation when Redis is unavailable

### Queue Workers

Background job framework (asyncio-based) supports:

- scraping jobs
- price history refresh
- price alerts
- cache warm-up

---

## 10) Error Handling Strategy

- Centralized exception handlers ensure JSON-safe errors
- LLM failures degrade gracefully via fallbacks
- Data/cache failures do not crash core API flow when recoverable

---

## 11) Local Development

### Requirements

- Python 3.11+ recommended
- pip

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

### Run server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run tests

```bash
python -m pytest -q
```

---

## 12) Docker

Build:

```bash
docker build -t smartcart-ai-backend .
```

Run:

```bash
docker run --rm -p 8000:8000 smartcart-ai-backend
```

---

## 13) Repository Structure

```text
app/
  agents/         # AI multi-agent logic
  api/            # FastAPI request/route layer
  orchestrator/   # Pipeline execution engine
  llm/            # LLM provider abstraction
  data/           # Product models and data access
  cache/          # Redis cache integration
  queue/          # Background worker system
  core/           # Config, security, exception handling
  response/       # Unified response builder
tests/            # Unit + integration + API tests
```

---

## 14) Additional Technical Docs

- **AI Logic documentation**: `app/agents/README.md`
- **FastAPI Backend documentation**: `app/api/README.md`
