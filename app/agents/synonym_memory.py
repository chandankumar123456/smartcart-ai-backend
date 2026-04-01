"""Synonym Memory Agent."""

from __future__ import annotations

from typing import Dict, Optional


class SynonymMemoryAgent:
    """In-memory synonym memory for canonical term recall and learning."""

    def __init__(self) -> None:
        self._memory: Dict[str, str] = {}

    async def lookup(self, term: str) -> Optional[str]:
        return self._memory.get(term.strip().lower())

    async def remember(self, raw_term: str, canonical_name: str) -> None:
        raw = raw_term.strip().lower()
        canonical = canonical_name.strip().lower()
        if raw and canonical:
            self._memory[raw] = canonical
