"""Synonym Memory Agent."""

from __future__ import annotations

from typing import Dict, List, Optional


class SynonymMemoryAgent:
    """In-memory synonym memory for canonical term recall and learning."""

    def __init__(self) -> None:
        self._memory: Dict[str, str] = {}
        self._reverse: Dict[str, List[str]] = {}

    async def lookup(self, term: str) -> Optional[str]:
        return self._memory.get(term.strip().lower())

    async def remember(self, raw_term: str, canonical_name: str) -> None:
        raw = raw_term.strip().lower()
        canonical = canonical_name.strip().lower()
        if raw and canonical:
            self._memory[raw] = canonical
            aliases = self._reverse.get(canonical, [])
            if raw not in aliases:
                aliases.append(raw)
            self._reverse[canonical] = aliases

    async def aliases_for(self, canonical_name: str) -> List[str]:
        return list(self._reverse.get(canonical_name.strip().lower(), []))
