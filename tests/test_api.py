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
        assert "/ai/search" in data["endpoints"]

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestSearchEndpoint:
    def test_search_valid_query(self, client):
        response = client.post("/ai/search", json={"query": "milk"})
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "milk"
        assert "results" in data
        assert "best_option" in data
        assert "deals" in data
        assert "total_price" in data

    def test_search_empty_query_rejected(self, client):
        response = client.post("/ai/search", json={"query": ""})
        assert response.status_code == 422

    def test_search_missing_query_rejected(self, client):
        response = client.post("/ai/search", json={})
        assert response.status_code == 422

    def test_search_with_price_filter_query(self, client):
        response = client.post("/ai/search", json={"query": "milk under 30"})
        assert response.status_code == 200
        data = response.json()
        for r in data["results"]:
            assert r["price"] <= 30.0

    def test_search_rice_has_results(self, client):
        response = client.post("/ai/search", json={"query": "rice"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0

    def test_search_generic_chicken_has_results(self, client):
        response = client.post("/ai/search", json={"query": "chicken"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0

    def test_search_generic_curd_alias_has_results(self, client):
        response = client.post("/ai/search", json={"query": "dahi"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0


class TestRecipeEndpoint:
    def test_recipe_valid_query(self, client):
        response = client.post("/ai/recipe", json={"query": "tomato pasta", "servings": 2})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total_price" in data

    def test_recipe_default_servings(self, client):
        response = client.post("/ai/recipe", json={"query": "fried rice"})
        assert response.status_code == 200

    def test_recipe_empty_query_rejected(self, client):
        response = client.post("/ai/recipe", json={"query": ""})
        assert response.status_code == 422

    def test_recipe_invalid_servings_rejected(self, client):
        response = client.post("/ai/recipe", json={"query": "pasta", "servings": 0})
        assert response.status_code == 422


class TestCartOptimizeEndpoint:
    def test_cart_optimize_valid(self, client):
        response = client.post(
            "/ai/cart-optimize",
            json={"items": [{"name": "milk", "quantity": 1}, {"name": "bread", "quantity": 2}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total_price" in data
        assert data["total_price"] > 0

    def test_cart_optimize_empty_items_rejected(self, client):
        response = client.post("/ai/cart-optimize", json={"items": []})
        assert response.status_code == 422

    def test_cart_optimize_missing_items_rejected(self, client):
        response = client.post("/ai/cart-optimize", json={})
        assert response.status_code == 422

    def test_cart_optimize_metadata(self, client):
        response = client.post(
            "/ai/cart-optimize",
            json={"items": [{"name": "rice"}, {"name": "onion"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["intent"] == "cart_optimize"
