"""Recipe Agent.

Handles recipe queries: generates ingredient lists, checks availability,
finds cheapest product sources, and builds an optimised cart.

README
------
Transforms food planning into actionable grocery decisions.
Input: recipe query string
Output: RecipeResult with ingredients + mapped products + optimised cart
"""

from typing import Any, Dict, List, Optional

from app.agents.normalization import NormalizationAgent
from app.core.exceptions import AgentException
from app.data.layer import get_products_for_entity
from app.data.models import Ingredient, IngredientProduct, PlatformProduct, RecipeResult
from app.llm.manager import LLMManager

_SCHEMA_EXAMPLE = """{
  "recipe_name": "Tomato Pasta",
  "servings": 2,
  "ingredients": [
    {"name": "pasta", "quantity": "200", "unit": "g"},
    {"name": "tomato", "quantity": "3", "unit": "pcs"},
    {"name": "onion", "quantity": "1", "unit": "pcs"},
    {"name": "oil", "quantity": "2", "unit": "tbsp"},
    {"name": "salt", "quantity": "1", "unit": "tsp"}
  ]
}"""

_PROMPT_TEMPLATE = """
You are a recipe and grocery assistant.

The user wants to make: "{query}"
Servings: {servings}

Return a JSON with:
- recipe_name: name of the dish
- servings: number of servings
- ingredients: list of ingredients, each with:
  - name: ingredient name (single english word preferred, e.g. "tomato", "milk", "onion")
  - quantity: numeric quantity as string
  - unit: unit (g, ml, pcs, tbsp, tsp, kg, L, cups)

Keep ingredients practical and to the point for Indian grocery stores.
"""

# Fallback static recipes for common dishes
_STATIC_RECIPES: Dict[str, Dict[str, Any]] = {
    "tomato pasta": {
        "recipe_name": "Tomato Pasta",
        "servings": 2,
        "ingredients": [
            {"name": "pasta", "quantity": "200", "unit": "g"},
            {"name": "tomato", "quantity": "3", "unit": "pcs"},
            {"name": "onion", "quantity": "1", "unit": "pcs"},
            {"name": "oil", "quantity": "2", "unit": "tbsp"},
        ],
    },
    "fried rice": {
        "recipe_name": "Fried Rice",
        "servings": 2,
        "ingredients": [
            {"name": "rice", "quantity": "1", "unit": "cup"},
            {"name": "eggs", "quantity": "2", "unit": "pcs"},
            {"name": "onion", "quantity": "1", "unit": "pcs"},
            {"name": "oil", "quantity": "2", "unit": "tbsp"},
        ],
    },
    "dal": {
        "recipe_name": "Dal",
        "servings": 4,
        "ingredients": [
            {"name": "tomato", "quantity": "2", "unit": "pcs"},
            {"name": "onion", "quantity": "1", "unit": "pcs"},
            {"name": "oil", "quantity": "2", "unit": "tbsp"},
        ],
    },
}


def _find_static_recipe(query: str) -> Dict[str, Any]:
    q = query.lower().strip()
    for key, recipe in _STATIC_RECIPES.items():
        if key in q or q in key:
            return recipe
    # Generic fallback
    return {
        "recipe_name": query.title(),
        "servings": 2,
        "ingredients": [
            {"name": "tomato", "quantity": "2", "unit": "pcs"},
            {"name": "onion", "quantity": "1", "unit": "pcs"},
            {"name": "oil", "quantity": "1", "unit": "tbsp"},
        ],
    }


def _cheapest_product(products: List[PlatformProduct]) -> Optional[PlatformProduct]:
    in_stock = [p for p in products if p.in_stock]
    return min(in_stock, key=lambda p: p.price) if in_stock else None


class RecipeAgent:
    """Handles recipe queries end-to-end.

    README: Transforms planning into actionable grocery decisions.
    """

    def __init__(self, llm_manager: LLMManager) -> None:
        self._llm = llm_manager
        self._normalizer = NormalizationAgent(llm_manager)

    async def run(self, query: str, servings: int = 2) -> RecipeResult:
        if not query or not query.strip():
            raise AgentException("RecipeAgent", "Empty recipe query")

        # Step 1: Generate ingredient list
        raw_recipe = await self._get_recipe(query, servings)

        # Step 2: Map ingredients to products
        ingredient_products = await self._map_ingredients(raw_recipe.get("ingredients", []))

        # Step 3: Compute total estimated cost
        total_cost = sum(
            ip.cheapest_option.price for ip in ingredient_products if ip.cheapest_option
        )

        # Step 4: Find missing items (no products found)
        missing = [
            ip.ingredient.name
            for ip in ingredient_products
            if not ip.matched_products
        ]

        return RecipeResult(
            recipe_name=raw_recipe.get("recipe_name", query.title()),
            servings=raw_recipe.get("servings", servings),
            ingredients=ingredient_products,
            total_estimated_cost=round(total_cost, 2),
            missing_items=missing,
        )

    async def _get_recipe(self, query: str, servings: int) -> Dict[str, Any]:
        prompt = _PROMPT_TEMPLATE.format(query=query.strip(), servings=servings)
        try:
            result = await self._llm.call(prompt, schema_example=_SCHEMA_EXAMPLE)
            if not result.get("ingredients"):
                raise ValueError("No ingredients returned")
            return result
        except Exception:
            return _find_static_recipe(query)

    async def _map_ingredients(self, raw_ingredients: list) -> List[IngredientProduct]:
        result = []
        for raw in raw_ingredients:
            ingredient = Ingredient(
                name=raw.get("name", ""),
                quantity=str(raw.get("quantity", "1")),
                unit=raw.get("unit", "pcs"),
            )
            normalized = await self._normalizer.run(ingredient.name)
            products = get_products_for_entity(normalized.canonical_name)
            cheapest = _cheapest_product(products)
            result.append(
                IngredientProduct(
                    ingredient=ingredient,
                    matched_products=products,
                    cheapest_option=cheapest,
                )
            )
        return result
