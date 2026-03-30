"""Request validation utilities for API handlers.

README
------
Ensures clean, validated input before it reaches the agent pipeline.
"""

from typing import List

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.data.models import CartItem


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural language grocery search query")

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query must not be empty or whitespace")
        return stripped


class RecipeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Recipe name or description")
    servings: int = Field(default=2, ge=1, le=20, description="Number of servings")

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Recipe query must not be empty or whitespace")
        return stripped


class CartOptimizeRequest(BaseModel):
    items: List[CartItem] = Field(..., min_length=1, description="List of grocery items to optimise")

    @field_validator("items")
    @classmethod
    def validate_items(cls, v: List[CartItem]) -> List[CartItem]:
        if not v:
            raise ValueError("Items list must not be empty")
        seen = set()
        clean = []
        for item in v:
            key = item.name.lower().strip()
            if key and key not in seen:
                seen.add(key)
                item.name = item.name.strip()
                clean.append(item)
        if not clean:
            raise ValueError("No valid items provided")
        return clean


def require_non_empty_query(query: str) -> str:
    """Raise 400 if query is empty after stripping."""
    if not query or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query must not be empty",
        )
    return query.strip()
