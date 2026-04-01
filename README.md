# SmartCart AI Backend

SmartCart AI Backend is a database-first, scraper-backed grocery intelligence platform.

## 1. System Architecture

```text
Scraper Scheduler → Scraper Workers → Data Cleaning → PostgreSQL
            → AI Parse/Normalize/Match/Rank/Evaluate
            → Results + Store Redirection
```

Request path:

```text
User Query
  → /parse-query (intelligence contract)
  → /search (execution from FinalStructuredQuery only)
  → DB lookup (primary)
  → Optional API fallback (if DB miss)
  → Ranking + evaluation
  → response with link_status and source
```

## 2. Data Pipeline

```text
scheduler → queue job → scraper extract → cleaning/normalization → DB upsert → AI search/ranking
```

- Scheduler: `app/jobs/scheduler.py`
- Queue workers: `app/queue/worker.py`
- Blinkit scraper entry: `app/scrapers/blinkit_scraper.py`
- Data access + fallback: `app/data/layer.py`

## 3. Database Schema

Defined in `app/data/database.py` (`products` table):

- `id` (PK)
- `product_id` (source platform identifier)
- `product_name`
- `normalized_name`
- `brand`
- `category`
- `price`
- `platform` (`blinkit/zepto/instamart/bigbasket/...`)
- `product_url` (stored exactly as scraped; nullable)
- `delivery_time` (optional)
- `rating` (optional)
- `original_price` (optional)
- `discount_percent` (optional)
- `unit` (optional)
- `in_stock`
- `source` (`db` or `api`)
- `last_updated`

## 4. Scraper System

- Tooling: `httpx` + `BeautifulSoup` (Blinkit-first implementation)
- Pipeline behavior:
  1. Fetch listing HTML
  2. Extract product fields (`id`, `name`, `price`, `url`)
  3. Clean and shape records
  4. Upsert into PostgreSQL
- Frequency: `SCRAPER_INTERVAL_MINUTES` (default 180)
- Freshness model: latest `last_updated` per product record

## 5. API Design

### Endpoints

- `POST /parse-query` → returns `FinalStructuredQuery`
- `POST /search` → executes from `FinalStructuredQuery`
- `POST /execute` → alias for `/search`
- `POST /recipe`
- `POST /cart-optimization`
- `POST /platform-events`

### Search response product fields

Each product result includes:
- `name`
- `brand`
- `price`
- `platform`
- `delivery_time_minutes` (if available)
- `url`
- `link_status` (`available` or `link unavailable`)
- `source` (`db` or `api`)

## 6. Agent System

Main orchestrator: `app/orchestrator/pipeline.py`

Core agents:
- language processing
- intent detection
- entity extraction
- normalization (synonyms/canonicalization)
- ambiguity reasoning
- product matching
- ranking
- deal detection
- evaluation and bounded retry

## 7. Ranking Logic

Weights (default):
- price: 40% (primary)
- delivery: 30%
- rating: 20%
- discount: 10%

Constraint-driven preference weights can override defaults.

## 8. Cart Optimization

For multi-item carts:
- computes product candidates per item
- estimates per-platform subtotals
- computes optimized grouping and savings
- supports global objective using cost + delivery weighting

## 9. Recipe System

Flow:
1. Parse recipe intent
2. Extract/generate ingredients
3. Normalize each ingredient
4. Match ingredient to DB products
5. Return platform-wise options and cheapest mapped option

## 10. Data Integrity Rules

- DB is the source of truth for core search.
- URLs are never fabricated.
- `product_url` is persisted exactly as scraped/API supplied.
- If URL is missing: response marks `link_status="link unavailable"`.

## 11. Fallback Strategy

If DB has no matching records:
- optional external API fallback may be used
- fallback requests use retry + backoff on 429/transport errors
- fallback records are persisted back to DB for future queries
- returned records are marked `source="api"`

If DB has records:
- use DB records
- mark `source="db"`

## 12. Reliability & Error Handling

- Redis cache is optional; service runs with Redis unavailable.
- Rate limit enforcement is active at API layer (429 response).
- External API fallback retries with exponential backoff.
- Ambiguity does not trigger for single high-confidence entities.
- Evaluation avoids marking valid single-entity unavailable results as ambiguity failure.

## 13. Limitations

- Freshness depends on scheduler cadence and scraper success.
- Platform HTML changes can reduce scraper extraction quality.
- Some products may legitimately have no URL from source; these are returned as unavailable links.

## 14. Deployment Guide

1. Configure `.env`:
   - `DATABASE_URL`
   - `DB_SCHEMA_AUTO_CREATE`
   - `SCRAPER_ENABLED`
   - `SCRAPER_INTERVAL_MINUTES`
   - `SCRAPER_BLINKIT_URL`
   - `API_FALLBACK_ENABLED`
   - `EXTERNAL_PRODUCT_API_URL`
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run backend:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. (Optional) Disable local mock fallback in production:
   - set `MOCK_DATA_ENABLED=false`

## Testing

```bash
python -m pytest -q
```
