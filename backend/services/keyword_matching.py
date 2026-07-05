"""Pure keyword matching primitives shared by runtime adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional


@dataclass(frozen=True)
class KeywordMatch:
    list_name: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class KeywordCatalog:
    """Immutable keyword lists grouped by application or tenant scope."""

    scopes: Mapping[str, Mapping[str, tuple[str, ...]]]

    @classmethod
    def empty(cls) -> "KeywordCatalog":
        return cls(scopes={})

    @classmethod
    def from_records(cls, records: Iterable[object]) -> "KeywordCatalog":
        scopes: dict[str, dict[str, tuple[str, ...]]] = {}
        for record in records:
            scope_id = getattr(record, "application_id", None)
            if not scope_id:
                continue
            keywords = normalize_keywords(getattr(record, "keywords", None))
            if not keywords:
                continue
            scopes.setdefault(str(scope_id), {})[str(record.name)] = keywords
        return cls(scopes=scopes)

    def search(self, scope_id: Optional[str], content: str) -> Optional[KeywordMatch]:
        if not scope_id:
            return None

        folded_content = content.casefold()
        for list_name, keywords in self.scopes.get(str(scope_id), {}).items():
            hits = tuple(keyword for keyword in keywords if keyword in folded_content)
            if hits:
                return KeywordMatch(list_name=list_name, keywords=hits)
        return None

    @property
    def list_count(self) -> int:
        return sum(len(lists) for lists in self.scopes.values())

    @property
    def keyword_count(self) -> int:
        return sum(len(keywords) for lists in self.scopes.values() for keywords in lists.values())


def normalize_keywords(raw_keywords: object) -> tuple[str, ...]:
    if not isinstance(raw_keywords, list):
        return ()

    unique_keywords: dict[str, None] = {}
    for keyword in raw_keywords:
        if not isinstance(keyword, str):
            continue
        normalized = keyword.strip().casefold()
        if normalized:
            unique_keywords.setdefault(normalized, None)
    return tuple(unique_keywords)
