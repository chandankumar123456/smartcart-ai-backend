"""Language Processing Agent."""

from __future__ import annotations

import re
import unicodedata

from app.data.models import CleanQuery

_NOISE_TOKENS = {"pls", "plz", "please", "hey", "hi", "hello", "bhai", "yaar"}
_TOKEN_CLEAN = re.compile(r"[^\w₹\s\.]", re.UNICODE)


class LanguageProcessingAgent:
    """Normalizes and tokenizes raw user text."""

    async def run(self, query: str) -> CleanQuery:
        text = unicodedata.normalize("NFKC", query).lower().strip()
        text = _TOKEN_CLEAN.sub(" ", text)
        tokens = [t for t in text.split() if t and t not in _NOISE_TOKENS]
        normalized = " ".join(tokens)
        return CleanQuery(
            text=query.strip(),
            language="en",
            tokens=tokens,
            normalized_text=normalized,
        )
