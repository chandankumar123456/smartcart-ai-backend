"""Query Understanding Agent.

Entry point of the intelligence pipeline.
Converts natural language → structured StructuredQuery JSON.

README
------
All downstream agents depend on this agent's output.
It ALWAYS returns a StructuredQuery (never raw text).
If the LLM is unavailable, a rule-based fallback ensures the pipeline continues.
"""

import logging
import re
from typing import Any, Dict

from app.core.exceptions import AgentException
from app.data.models import QueryFilters, QueryIntent, StructuredQuery
from app.llm.manager import LLMManager

_SCHEMA_EXAMPLE = """{
  "product": "milk",
  "filters": {
    "max_price": 60,
    "min_price": null,
    "category": "dairy",
    "quantity": "500ml",
    "brand": null
  },
  "intent": "product_search"
}"""

_PROMPT_TEMPLATE = """
Extract structured information from the grocery query below.

Query: "{query}"

Return JSON with fields:
- product (string): primary product name
- filters.max_price (number|null): maximum price if mentioned
- filters.min_price (number|null): minimum price if mentioned
- filters.category (string|null): category if mentioned
- filters.quantity (string|null): quantity/size if mentioned
- filters.brand (string|null): brand if mentioned
- intent (string): one of "product_search", "recipe", "deal_search", "cart_optimize"

Intent rules:
- "recipe" if query mentions recipe, cook, make, prepare, or dish names
- "deal_search" if query mentions deals, offers, discounts, sale, cheap
- "cart_optimize" if query mentions optimize, cart, total, basket
- otherwise "product_search"
"""

# Simple keyword rules for rule-based fallback
_PRICE_PATTERN = re.compile(r"(?:under|below|less than|<|max|upto)\s*(?:rs\.?|₹)?\s*(\d+(?:\.\d+)?)", re.I)
_RECIPE_KEYWORDS = {"recipe", "cook", "prepare", "make", "dish", "biryani", "curry", "pasta", "soup", "salad"}
_DEAL_KEYWORDS = {"deal", "offers", "discount", "sale", "cashback", "coupon"}
_CART_KEYWORDS = {"optimize", "cart", "basket", "total cost", "split"}

_KNOWN_PRODUCTS = {
    "milk", "bread", "eggs", "rice", "tomato", "onion", "oil", "butter",
    "pasta", "sugar", "atta", "flour", "salt", "tea", "coffee", "biscuits",
    "chips", "noodles", "cheese", "yogurt", "curd", "chicken", "ghee",
}

logger = logging.getLogger(__name__)


def _rule_based_parse(query: str) -> Dict[str, Any]:
    """Simple rule-based fallback when LLM is unavailable."""
    q = query.lower().strip()

    # Detect intent
    if any(k in q for k in _RECIPE_KEYWORDS):
        intent = QueryIntent.recipe
    elif any(k in q for k in _DEAL_KEYWORDS):
        intent = QueryIntent.deal_search
    elif any(k in q for k in _CART_KEYWORDS):
        intent = QueryIntent.cart_optimize
    else:
        intent = QueryIntent.product_search

    # Extract product (first known product word, or first token)
    product = ""
    for word in q.split():
        if word in _KNOWN_PRODUCTS:
            product = word
            break
    if not product:
        # Use the longest token that is not a stopword
        stopwords = {"find", "show", "get", "best", "cheap", "buy", "need", "want", "for", "me", "the", "a", "an"}
        tokens = [t.strip(".,!?") for t in q.split() if t.strip(".,!?") not in stopwords]
        product = tokens[0] if tokens else q

    # Extract max_price
    match = _PRICE_PATTERN.search(q)
    max_price = float(match.group(1)) if match else None

    return {
        "product": product,
        "filters": {
            "max_price": max_price,
            "min_price": None,
            "category": None,
            "quantity": None,
            "brand": None,
        },
        "intent": intent.value,
    }


class QueryUnderstandingAgent:
    """Converts raw user query into a StructuredQuery.

    Tries LLM first; falls back to rule-based parsing on failure.
    """

    def __init__(self, llm_manager: LLMManager) -> None:
        self._llm = llm_manager

    async def run(self, raw_query: str) -> StructuredQuery:
        if not raw_query or not raw_query.strip():
            raise AgentException("QueryUnderstandingAgent", "Empty query received")

        prompt = _PROMPT_TEMPLATE.format(query=raw_query.strip())
        llm_called = False

        try:
            llm_called = True
            parsed = await self._llm.call(prompt, schema_example=_SCHEMA_EXAMPLE)
            logger.debug("[QUERY_AGENT] llm_called=%s raw_output=%s", llm_called, parsed)
            parsed = self._validate_parsed(parsed, raw_query)
            logger.debug("[PARSE_CHECK] success=true reason=")
        except Exception:
            logger.debug("[PARSE_CHECK] success=false reason=llm_or_validation_failed")
            parsed = _rule_based_parse(raw_query)
        logger.debug("[QUERY_AGENT] parsed_query=%s llm_called=%s", parsed, llm_called)

        return StructuredQuery(
            product=parsed.get("product", raw_query),
            filters=QueryFilters(**{
                k: parsed.get("filters", {}).get(k)
                for k in QueryFilters.model_fields
            }),
            intent=QueryIntent(parsed.get("intent", QueryIntent.product_search.value)),
            raw_query=raw_query,
        )

    @staticmethod
    def _validate_parsed(parsed: Dict[str, Any], raw_query: str) -> Dict[str, Any]:
        """Ensure required fields exist and are valid."""
        if not isinstance(parsed.get("product"), str) or not parsed["product"]:
            parsed["product"] = raw_query.split()[0] if raw_query.split() else raw_query
        valid_intents = {i.value for i in QueryIntent}
        if parsed.get("intent") not in valid_intents:
            parsed["intent"] = QueryIntent.product_search.value
        if "filters" not in parsed or not isinstance(parsed["filters"], dict):
            parsed["filters"] = {}
        return parsed
