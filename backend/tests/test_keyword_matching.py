from dataclasses import dataclass

from services.keyword_matching import KeywordCatalog, normalize_keywords


@dataclass
class KeywordRecord:
    application_id: str
    name: str
    keywords: object


def test_normalize_keywords_is_case_insensitive_and_stable():
    assert normalize_keywords([" Alpha ", "alpha", "", None, "Beta"]) == ("alpha", "beta")


def test_catalog_matches_within_requested_scope_only():
    catalog = KeywordCatalog.from_records(
        [
            KeywordRecord("app-a", "restricted", ["Project Cedar"]),
            KeywordRecord("app-b", "restricted", ["Project Maple"]),
        ]
    )

    match = catalog.search("app-a", "Discuss PROJECT CEDAR tomorrow")

    assert match is not None
    assert match.list_name == "restricted"
    assert match.keywords == ("project cedar",)
    assert catalog.search("app-b", "Discuss PROJECT CEDAR tomorrow") is None


def test_catalog_ignores_records_without_scope_or_keywords():
    catalog = KeywordCatalog.from_records(
        [
            KeywordRecord("", "missing-scope", ["alpha"]),
            KeywordRecord("app-a", "missing-keywords", None),
        ]
    )

    assert catalog.list_count == 0
    assert catalog.keyword_count == 0
