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

### Intelligence + Execution Pipeline

```text
User Query
  → LanguageProcessingAgent
  → IntentDetectionAgent
  → EntityExtractionAgent
  → NormalizationAgent
  → ConstraintExtractionAgent
  → DomainGuardAgent
  → FallbackAgent
  → OutputFormatterAgent
  → (FinalStructuredQuery complete)
  → ProductMatchingAgent
  → RankingAgent
  → DealDetectionAgent
  → ResponseBuilder
```

Guarantee: execution never starts before `FinalStructuredQuery` is finalized.

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

### `POST /parse-query`
Intelligence-layer endpoint. Returns machine-usable structured query contract.

Request:

```json
{
  "query": "cheap milk under 35"
}
```

### `POST /search`
Execution-layer endpoint. Internally runs `/parse-query` stage first, then matching/ranking/deals.

Request:

```json
{
  "query": "cheap milk under 35"
}
```

### `POST /recipe`
Converts recipe intent into ingredient list + mapped products.

Request:

```json
{
  "query": "tomato pasta",
  "servings": 2
}
```

### `POST /cart-optimization`
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

## 7) Strict Data Contracts

All intelligence stages use explicit machine-consumable schemas from `app/data/models.py`.

- `CleanQuery`: normalized text, language, and token list.
- `IntentResult`: classified intent + confidence + notes.
- `RawEntities`: extracted entities with ambiguity flags.
- `NormalizedEntities`: canonical entities + unresolved entity list.
- `Constraints`: budget/servings/preferences + ranking preference weights.
- `DomainGuardResult`: allow/block decision with confidence and reason.
- `FallbackDecision`: fallback mode/reason/alternatives.
- `FinalStructuredQuery`: all intelligence outputs + `StructuredQuery`.

`/parse-query` returns `FinalStructuredQuery` directly.

---

## 8) Agent Responsibilities

- `LanguageProcessingAgent` — query cleaning/tokenization.
- `IntentDetectionAgent` — intent classification.
- `EntityExtractionAgent` — raw entity extraction.
- `NormalizationAgent` — canonical item mapping + synonym learning.
- `ConstraintExtractionAgent` — budget/servings/preferences extraction.
- `DomainGuardAgent` — grocery-domain safety gating.
- `FallbackAgent` — ambiguity/exploratory fallback strategy.
- `OutputFormatterAgent` — final strict structured output assembly.
- `SynonymMemoryAgent` — remembers raw-term → canonical mappings.
- `QueryLoggingAgent` — stage-wise structured observability logs.

---

## 9) System Guarantees

- No raw entities are sent to matching/ranking.
- No execution before structured intelligence is finalized.
- Unsupported domain queries are blocked by domain guard with structured metadata.
- Exploratory/vague queries are handled via fallback mode with alternatives.
- Structured output remains deterministic JSON across all endpoints.

---

## 10) Standard Response Contract

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

## 11) Configuration

Environment configuration lives in `.env` (see `.env.example`):

- App: `DEBUG`
- Security: `API_KEYS`, rate limit settings
- LLM: provider and model keys/settings
- Redis: URL + TTL
- Data mode: mock/preprocessed switch

Core settings class: `app/core/config.py`.

---

## 12) Caching & Queue Design

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

## 13) Error Handling Strategy

- Centralized exception handlers ensure JSON-safe errors
- LLM failures degrade gracefully via fallbacks
- Data/cache failures do not crash core API flow when recoverable

---

## 14) Local Development

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

## 15) Docker

Build:

```bash
docker build -t smartcart-ai-backend .
```

Run:

```bash
docker run --rm -p 8000:8000 smartcart-ai-backend
```

---

## 16) Repository Structure

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

## 17) Additional Technical Docs

- **AI Logic documentation**: `app/agents/README.md`
- **FastAPI Backend documentation**: `app/api/README.md`
