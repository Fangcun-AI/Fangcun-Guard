from services.request_context import AnonymizationContext, restore_placeholders


def setup_function():
    AnonymizationContext.clear()


def test_mapping_updates_are_merged_and_restored():
    AnonymizationContext.set_mapping({"[email_1]": "dev@example.com"})
    AnonymizationContext.set_mapping({"[name_1]": "Dev"})

    assert restore_placeholders("Send [name_1] at [email_1]") == "Send Dev at dev@example.com"


def test_counters_are_isolated_from_returned_dictionary():
    assert AnonymizationContext.get_next_counter("email") == 1
    returned = AnonymizationContext.get_counters()
    returned["email"] = 99

    assert AnonymizationContext.get_next_counter("email") == 2


def test_clear_removes_mappings_and_counters():
    AnonymizationContext.set_mapping({"[email_1]": "dev@example.com"})
    AnonymizationContext.get_next_counter("email")

    AnonymizationContext.clear()

    assert AnonymizationContext.has_mapping() is False
    assert AnonymizationContext.get_counters() == {}
