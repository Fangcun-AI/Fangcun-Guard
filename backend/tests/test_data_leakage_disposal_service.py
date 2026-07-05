from types import SimpleNamespace

from services.data_leakage_disposal_service import LeakageMitigator


class StubLeakageMitigator(LeakageMitigator):
    def __init__(self, app_policy=None, tenant_policy=None, private_model=None):
        self.app_policy = app_policy
        self.tenant_policy = tenant_policy
        self.private_model = private_model

    def get_disposal_policy(self, application_id):
        return self.app_policy

    def get_tenant_policy(self, tenant_id):
        return self.tenant_policy

    def get_private_model(self, application_id, tenant_id):
        return self.private_model


def test_disposal_action_uses_application_override_before_tenant_default():
    service = StubLeakageMitigator(
        app_policy=SimpleNamespace(
            tenant_id="tenant-a", input_medium_risk_action="anonymize_restore"
        ),
        tenant_policy=SimpleNamespace(default_input_medium_risk_action="block"),
    )

    assert service.get_disposal_action("app-a", "medium_risk") == "anonymize_restore"


def test_output_disposal_falls_back_to_safe_defaults_without_policy():
    service = StubLeakageMitigator()

    assert service.get_disposal_action("app-a", "high_risk", "output") == "block"
    assert service.get_disposal_action("app-a", "medium_risk", "output") == "anonymize"
    assert service.get_disposal_action("app-a", "low_risk", "output") == "pass"


def test_general_action_supports_directional_and_legacy_defaults():
    service = StubLeakageMitigator(
        app_policy=SimpleNamespace(tenant_id="tenant-a"),
        tenant_policy=SimpleNamespace(default_general_medium_risk_action="replace"),
    )

    assert service.get_general_risk_action("app-a", "medium_risk", "output") == "replace"


def test_policy_settings_preserve_explicit_false_override():
    service = StubLeakageMitigator(
        app_policy=SimpleNamespace(
            tenant_id="tenant-a",
            enable_format_detection=False,
            enable_smart_segmentation=None,
        ),
        tenant_policy=SimpleNamespace(
            default_enable_format_detection=True,
            default_enable_smart_segmentation=False,
        ),
    )

    assert service.get_policy_settings("app-a") == {
        "enable_format_detection": False,
        "enable_smart_segmentation": False,
    }


def test_private_model_validation_requires_available_model():
    assert StubLeakageMitigator().validate_disposal_action(
        "switch_private_model", "tenant-a", "app-a"
    )[0] is False
    assert StubLeakageMitigator(private_model=object()).validate_disposal_action(
        "switch_private_model", "tenant-a", "app-a"
    ) == (True, "")
