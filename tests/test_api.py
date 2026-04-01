"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    # Patch Redis and queue to avoid real connections during tests
    with (
        patch("app.cache.redis_cache.CacheLayer.connect", new_callable=AsyncMock),
        patch("app.cache.redis_cache.CacheLayer.disconnect", new_callable=AsyncMock),
        patch("app.queue.worker.JobQueue.start", new_callable=AsyncMock),
        patch("app.queue.worker.JobQueue.stop", new_callable=AsyncMock),
        patch("app.cache.redis_cache.CacheLayer.get", new_callable=AsyncMock, return_value=None),
        patch("app.cache.redis_cache.CacheLayer.set", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


class TestHealthEndpoints:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "/search" in data["endpoints"]

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestSearchEndpoint:
    def _parse_payload(self, client, query: str):
        response = client.post("/parse-query", json={"query": query})
        assert response.status_code == 200
        return response.json()

    def test_search_valid_query(self, client):
        payload = self._parse_payload(client, "milk")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "milk"
        assert "results" in data
        assert "best_option" in data
        assert "deals" in data
        assert "total_price" in data

    def test_search_empty_query_rejected(self, client):
        response = client.post("/search", json={})
        assert response.status_code == 422

    def test_search_missing_query_rejected(self, client):
        response = client.post("/search", json={"foo": "bar"})
        assert response.status_code == 422

    def test_search_with_price_filter_query(self, client):
        payload = self._parse_payload(client, "milk under 30")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        for r in data["results"]:
            assert r["price"] <= 30.0

    def test_search_rice_has_results(self, client):
        payload = self._parse_payload(client, "rice")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0

    def test_search_generic_chicken_has_results(self, client):
        payload = self._parse_payload(client, "chicken")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0

    def test_search_generic_curd_alias_has_results(self, client):
        payload = self._parse_payload(client, "dahi")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0

    def test_search_capsicum_has_results(self, client):
        payload = self._parse_payload(client, "capsicum")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0

    def test_search_paneer_cubes_has_results(self, client):
        payload = self._parse_payload(client, "paneer cubes")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0

    def test_search_evening_snacks_has_results(self, client):
        payload = self._parse_payload(client, "something for evening snacks")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0
        assert data["metadata"]["intent"] == "exploratory"

    def test_search_unsupported_query(self, client):
        payload = self._parse_payload(client, "best laptop under 50000")
        response = client.post("/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["metadata"]["domain_guard"]["allowed"] is False

    def test_parse_query_returns_structured_contract(self, client):
        response = client.post("/parse-query", json={"query": "cheap milk under 60"})
        assert response.status_code == 200
        data = response.json()
        assert "clean_query" in data
        assert "intent_result" in data
        assert "raw_entities" in data
        assert "normalized_entities" in data
        assert "constraints" in data
        assert "domain_guard" in data
        assert "ambiguity" in data
        assert "fallback" in data
        assert "execution_plan" in data
        assert "execution_graph" in data
        assert "candidate_paths" in data
        assert "user_context" in data
        assert "learning_signals" in data
        assert "evaluation_history" in data
        assert "failure_policies" in data
        assert "platform_signals" in data
        assert "coordination_trace" in data
        assert "structured_query" in data

    def test_platform_events_ingestion_endpoint(self, client):
        response = client.post(
            "/platform-events",
            json={
                "event_type": "user.behavior",
                "user_id": "anonymous",
                "payload": {"action": "click", "item": "milk"},
                "source": "test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("accepted") is True

    def test_execute_endpoint_accepts_final_structured_query(self, client):
        payload = self._parse_payload(client, "milk")
        response = client.post("/execute", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "metadata" in data

    def test_parse_query_multi_intent_contains_secondary_intents(self, client):
        response = client.post("/parse-query", json={"query": "plan pasta and optimize my cart"})
        assert response.status_code == 200
        data = response.json()
        assert data["intent_result"]["intent"] == "recipe"
        assert "cart_optimization" in data["intent_result"]["secondary_intents"]


class TestRecipeEndpoint:
    def test_recipe_valid_query(self, client):
        response = client.post("/recipe", json={"query": "tomato pasta", "servings": 2})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total_price" in data

    def test_recipe_default_servings(self, client):
        response = client.post("/recipe", json={"query": "fried rice"})
        assert response.status_code == 200

    def test_recipe_empty_query_rejected(self, client):
        response = client.post("/recipe", json={"query": ""})
        assert response.status_code == 422

    def test_recipe_invalid_servings_rejected(self, client):
        response = client.post("/recipe", json={"query": "pasta", "servings": 0})
        assert response.status_code == 422


class TestCartOptimizeEndpoint:
    def test_cart_optimize_valid(self, client):
        response = client.post(
            "/cart-optimization",
            json={"items": [{"name": "milk", "quantity": 1}, {"name": "bread", "quantity": 2}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total_price" in data
        assert data["total_price"] > 0

    def test_cart_optimize_empty_items_rejected(self, client):
        response = client.post("/cart-optimization", json={"items": []})
        assert response.status_code == 422

    def test_cart_optimize_missing_items_rejected(self, client):
        response = client.post("/cart-optimization", json={})
        assert response.status_code == 422

    def test_cart_optimize_metadata(self, client):
        response = client.post(
            "/cart-optimization",
            json={"items": [{"name": "rice"}, {"name": "onion"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["intent"] == "cart_optimize"
