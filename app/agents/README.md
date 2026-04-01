# SmartCart Agent System Documentation

## 1. System Design

Agents operate in a strict DB-first architecture:

```text
Scraper → Cleaning → Database → Agent Pipeline → Ranking → Result + Redirection
```

Agents never fabricate product prices/links. They reason over structured data and constraints.

## 2. Core Agent Flow

Primary orchestrated sequence:

1. Language processing
2. Intent detection
3. Entity extraction
4. Normalization
5. Constraint extraction
6. Domain guard
7. Ambiguity reasoning
8. Execution planning
9. Product matching (DB-first)
10. Ranking
11. Deal detection
12. Evaluation/retry

## 3. Query Understanding

- Parses user text into `FinalStructuredQuery`
- Supports simple, budget, synonym, exploratory, recipe, and cart intents
- Structured execution contract prevents raw-query leakage into execution stage

## 4. Normalization

- Canonical mapping with synonym memory
- Includes stable mappings (e.g., `mayo` → `mayonnaise`)
- Outputs candidate variants for matching

## 5. Ambiguity Handling

Ambiguity is triggered only when appropriate:
- multiple possible entities
- low confidence
- conflicting interpretation flags

Single high-confidence entities skip ambiguity branching.

## 6. Product Matching

- DB-first matching through `app/data/layer.py`
- Optional API fallback if DB miss
- fallback records are persisted back to DB
- each product retains `source` marker (`db`/`api`)

## 7. Ranking Logic

Default weighted score:
- price 40%
- delivery 30%
- rating 20%
- discount 10%

Price is primary. Cheapest valid option can be highlighted.

## 8. Evaluation

- validates execution quality
- drives bounded retries
- avoids misclassifying valid single-entity unavailable outcomes as ambiguity failures

## 9. Cart Optimization

- computes best item options and grouped platform totals
- exposes total optimized cost and savings
- supports cross-platform optimization objective

## 10. Recipe to Product Mapping

- recipe/ingredient extraction
- per-ingredient normalization
- DB product match by ingredient
- platform-wise options and cheapest mapped item

## 11. Data Integrity Rules in Agents

- No synthetic links
- No fabricated prices or availability
- DB as source of truth for normal flow
- If link missing, response layer marks `link unavailable`

## 12. Reliability

- Works with Redis unavailable (cache no-op)
- Handles external fallback retries/backoff
- Maintains robust behavior under partial dependency failures

## 13. Limitations

- quality/freshness depends on scraper schedule and source site stability
- recipe ingredient coverage depends on DB catalog breadth

## 14. How to Run and Validate

```bash
pip install -r requirements.txt
python -m pytest -q tests/test_agents.py tests/test_pipeline.py
```
