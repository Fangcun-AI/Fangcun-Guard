from services.unified_anonymization_service import UnifiedAnonymizationService


def test_reversible_anonymization_replaces_longest_entity_first():
    service = UnifiedAnonymizationService()
    messages, mapping = service.anonymize_messages(
        [{"role": "user", "content": "mail user@example.com example.com"}],
        [
            {"text": "example.com", "entity_type": "domain"},
            {"text": "user@example.com", "entity_type": "email"},
        ],
        "anonymize_restore",
    )
    assert messages[0]["content"] == "mail __email_1__ __domain_1__"
    assert mapping == {
        "__email_1__": "user@example.com",
        "__domain_1__": "example.com",
    }


def test_one_way_anonymization_only_changes_user_messages():
    service = UnifiedAnonymizationService()
    messages, mapping = service.anonymize_messages(
        [
            {"role": "system", "content": "secret"},
            {"role": "user", "content": "secret"},
        ],
        [{"text": "secret", "entity_type": "token", "anonymized_value": "***"}],
        "anonymize",
    )
    assert [message["content"] for message in messages] == ["secret", "***"]
    assert mapping is None


def test_restore_content_applies_mapping():
    assert UnifiedAnonymizationService().restore_content(
        "hello __name_1__", {"__name_1__": "Alice"}
    ) == "hello Alice"
