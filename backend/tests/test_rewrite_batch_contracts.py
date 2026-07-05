from types import SimpleNamespace

from services.billing_service import BillingLedger
from services.content_scan_service import ContentInspector
from services.restore_anonymization_service import RestoreAnonymizationService
from services.stripe_service import StripeService


def test_stripe_url_normalization_and_checkout_parser():
    assert StripeService._url("'https://example.org/path'") == "https://example.org/path"
    assert StripeService._url("https://example.org/路径").endswith("%E8%B7%AF%E5%BE%84")
    event = {"data": {"object": {"id": "session", "customer": "customer", "metadata": {}}}}
    parsed = StripeService.__new__(StripeService).parse_checkout_completed(event)
    assert parsed["session_id"] == "session"
    assert parsed["customer_id"] == "customer"
    assert parsed["metadata"] == {}


def test_content_scan_response_parsing():
    inspector = ContentInspector()
    assert inspector._parse_response("safe") == []
    assert inspector._parse_response("unsafe\nE3,E1,UNKNOWN") == ["E3", "E1"]
    assert inspector._determine_risk_level(["E1"]) == "high"


def test_restore_code_cleanup_safety_and_mapping():
    service = RestoreAnonymizationService.__new__(RestoreAnonymizationService)
    assert service._parse_code_response("```python\nimport re\ndef anonymize(text):\n    return text\n```") == (
        "def anonymize(text):\n    return text"
    )
    assert not service._validate_code_safety("open('/tmp/data').read()")
    assert service.restore_text("hello [name_1]", {"[name_1]": "Ada"}) == "hello Ada"


def test_billing_period_start_handles_shorter_month():
    period_end = SimpleNamespace(month=3, year=2026)
    period_end.replace = lambda **values: values
    assert BillingLedger._period_start(period_end)["month"] == 2
