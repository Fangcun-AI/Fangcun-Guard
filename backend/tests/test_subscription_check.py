from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import utils.subscription_check as subscription


class Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *_conditions):
        return self

    def first(self):
        return self.value


class Db:
    def __init__(self, tenant=None, plan=None):
        self.values = [tenant, plan]

    def query(self, _model):
        return Query(self.values.pop(0))


def setup_function():
    subscription.settings = SimpleNamespace(is_enterprise_mode=False)


def test_enterprise_mode_enables_every_feature():
    subscription.settings.is_enterprise_mode = True
    result = subscription.get_feature_availability("ignored", None)
    assert result["is_subscribed"]
    assert all(result["features"].values())


def test_expired_plan_returns_localized_denial():
    expired = SimpleNamespace(
        subscription_type="subscribed",
        subscription_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    allowed, message = subscription.check_subscription_for_feature(
        "00000000-0000-0000-0000-000000000001",
        Db(plan=expired),
        subscription.SubscriptionFeature.FORMAT_DETECTION,
        "zh",
    )
    assert not allowed
    assert "订阅已过期" in message


def test_super_admin_has_access_without_plan():
    admin = SimpleNamespace(is_super_admin=True)
    allowed, message = subscription.check_subscription_for_feature(
        "00000000-0000-0000-0000-000000000001",
        Db(tenant=admin),
        subscription.SubscriptionFeature.CUSTOM_SCANNERS,
    )
    assert allowed and message is None
