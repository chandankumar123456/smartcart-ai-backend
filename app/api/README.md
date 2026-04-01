# SmartCart API Layer Documentation

## 1. Architecture Role

The API layer is the ingress and execution boundary around a DB-first grocery intelligence system.

```text
Client → FastAPI routes → security/rate-limit → orchestrator
      → DB-first data lookup → optional fallback → response
```

## 2. Data Pipeline Integration

The API path does not run full scraping at query time.

Data flow into responses is:

```text
scheduler → scraper worker → cleaning → PostgreSQL → API search execution
```

## 3. Database Contract in API Responses

Search responses expose DB/API provenance and link status:
- `source`: `db` or `api`
- `url`: real source URL only
- `link_status`: `available` or `link unavailable`

No generated URLs are returned.

## 4. Endpoints

- `POST /parse-query`
  - input: `{ "query": "..." }`
  - output: `FinalStructuredQuery`

- `POST /search`
  - input: `FinalStructuredQuery`
  - behavior: DB-first product match + ranking

- `POST /execute`
  - alias of `/search`

- `POST /recipe`
  - recipe to ingredients to platform product mapping

- `POST /cart-optimization`
  - split-cart and grouped platform optimization

- `POST /platform-events`
  - ingest platform/user/order/inventory/price signals

## 5. Search Flow

1. Parse query (`/parse-query`)
2. Execute using structured intelligence (`/search`)
3. Query PostgreSQL first
4. If DB miss and fallback enabled: call external API with retry/backoff and persist rows
5. Rank products
6. Return results with real/nullable links and source markers

## 6. Reliability Behaviors

- Redis caching is optional.
- Rate limiting returns HTTP 429 when exceeded.
- External fallback client retries with backoff.
- Service startup tolerates DB unavailability in degraded mode.

## 7. Security

- API key header based auth (`X-API-Key`) if keys configured.
- Proxy-aware IP extraction for rate limiting.

## 8. Operational Configuration

Important `.env` keys:
- `DATABASE_URL`
- `DB_SCHEMA_AUTO_CREATE`
- `MOCK_DATA_ENABLED` (set false in production)
- `SCRAPER_ENABLED`
- `SCRAPER_INTERVAL_MINUTES`
- `SCRAPER_BLINKIT_URL`
- `API_FALLBACK_ENABLED`
- `EXTERNAL_PRODUCT_API_URL`
- `API_FALLBACK_MAX_RETRIES`
- `API_FALLBACK_BACKOFF_SECONDS`

## 9. Testing

```bash
python -m pytest -q tests/test_api.py
```
