# AI Logic Documentation (Multi-Agent System)

This document defines the technical behavior of the **AI logic layer** implemented in `app/agents/`.

---

## 1) Purpose

The AI logic layer transforms:

```text
Natural Language Query → Structured Intent → Product Intelligence → Decision Output
```

This system is implemented as a **multi-agent pipeline** (not a single monolithic model).

---

## 2) Agent Design Principles

- Each agent has a **single responsibility**
- Input and output are **structured objects**
- Pipeline communication avoids unstructured/raw assistant text
- Agents are loosely coupled and can be extended independently
- Pipeline always converges to JSON-safe response objects

---

## 3) Implemented Agents

## 3.1 QueryUnderstandingAgent

**File:** `query_understanding.py`

### Responsibility
- Convert user query into `StructuredQuery`
- Detect intent:
  - `product_search`
  - `recipe`
  - `deal_search`
  - `cart_optimize`
- Extract filters (`max_price`, `min_price`, brand/category/quantity)

### Input
- Raw user text query

### Output
- `StructuredQuery` (`app/data/models.py`)

### Reliability behavior
- LLM-first parsing
- Rule-based fallback if LLM is unavailable/fails

---

## 3.2 ProductMatchingAgent

**File:** `product_matching.py`

### Responsibility
- Retrieve and normalize same entity across platforms
- Apply structured filters (price range, brand)

### Input
- `StructuredQuery`

### Output
- `UnifiedProduct` containing cross-platform `PlatformProduct` entries

---

## 3.3 RankingAgent

**File:** `ranking.py`

### Responsibility
- Score and rank matched products
- Select best option

### Input
- `UnifiedProduct`

### Output
- `RankingResult`

### Scoring factors (weighted)
- Price: 40%
- Delivery time: 30%
- Rating: 20%
- Discount: 10%

---

## 3.4 DealDetectionAgent

**File:** `deal_detection.py`

### Responsibility
- Identify savings opportunities from product set

### Input
- `UnifiedProduct`

### Output
- `DealResult`

### Rules
- Discount deal threshold: `>= 5%`
- Trending deal threshold: `>= 10%`

---

## 3.5 RecipeAgent

**File:** `recipe.py`

### Responsibility
- Handle recipe intent and convert into purchasable cart plan

### Flow
1. Generate ingredient list (LLM or static fallback)
2. Map ingredients to platform products
3. Pick cheapest options
4. Estimate total cost
5. Report missing ingredients when no product mapping exists

### Input
- Recipe query text (+ servings)

### Output
- `RecipeResult`

---

## 4) Pipeline Integration

Orchestrator entry: `app/orchestrator/pipeline.py`

Primary path:

```text
QueryUnderstandingAgent
  → ProductMatchingAgent
  → RankingAgent
  → DealDetectionAgent
```

Recipe branch:

```text
QueryUnderstandingAgent (intent=recipe)
  → RecipeAgent
```

---

## 5) Data Contracts Used by Agents

Defined in `app/data/models.py`:

- `StructuredQuery`
- `QueryFilters`
- `UnifiedProduct`
- `PlatformProduct`
- `RankingResult`
- `DealResult`
- `RecipeResult`
- `CartOptimizationResult`

All outputs are built to support consistent API responses via `FinalResponse`.

---

## 6) Advanced Intelligence Support

The AI logic layer includes foundational support for:

- Price history structures (`PriceHistory`, `PricePoint`)
- Price alert job hooks (queue handlers)
- Budget/cart optimization through split-order strategy
- Recipe-to-grocery conversion

---

## 7) Extension Guide

To add a new agent:

1. Create new file in `app/agents/`
2. Add/extend data contracts in `app/data/models.py` as needed
3. Inject execution step in `AgentPipeline`
4. Extend `ResponseBuilder` if output schema needs new metadata
5. Add focused tests in `tests/test_agents.py` and/or `tests/test_pipeline.py`

---

## 8) Testing Coverage

Relevant tests:

- `tests/test_agents.py` — unit tests per agent
- `tests/test_pipeline.py` — orchestrator integration tests

The current suite validates:

- intent detection and fallback behavior
- cross-platform matching
- ranking correctness
- deal detection thresholds
- recipe mapping and cost estimation

