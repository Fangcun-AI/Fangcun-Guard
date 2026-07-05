from services.format_detection_service import FormatProbe


def test_plain_text_is_not_misclassified_as_yaml():
    format_name, metadata = FormatProbe().detect_format("Please summarize this ordinary sentence.")

    assert format_name == "plain_text"
    assert metadata == {"line_count": 1}


def test_json_reports_nested_sensitive_paths():
    format_name, metadata = FormatProbe().detect_format(
        '{"profile": {"email": "dev@example.com"}, "display_name": "Dev"}'
    )

    assert format_name == "json"
    assert metadata["sensitive_paths"] == ["profile.email"]
    assert metadata["has_sensitive_fields"] is True


def test_csv_requires_consistent_columns():
    format_name, _ = FormatProbe().detect_format("email,name\ndev@example.com,Dev")
    inconsistent_name, _ = FormatProbe().detect_format("email,name\ndev@example.com")

    assert format_name == "csv"
    assert inconsistent_name == "plain_text"


def test_markdown_keeps_header_metadata():
    format_name, metadata = FormatProbe().detect_format("# Title\n\n- item")

    assert format_name == "markdown"
    assert metadata["headers"] == [{"level": 1, "title": "Title", "line": 0}]


def test_yaml_requires_structured_content():
    format_name, metadata = FormatProbe().detect_format("profile:\n  email: dev@example.com")

    assert format_name == "yaml"
    assert metadata["sensitive_paths"] == ["profile.email"]
