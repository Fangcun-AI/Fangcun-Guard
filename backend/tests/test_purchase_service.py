from types import SimpleNamespace

from services.purchase_service import PurchaseService


class Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *_conditions):
        return self

    def first(self):
        return self.value

    def all(self):
        return self.value


class Db:
    def __init__(self, *values):
        self.values = list(values)
        self.added = []
        self.commits = 0
        self.refreshed = []

    def query(self, _model):
        return Query(self.values.pop(0))

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def refresh(self, value):
        self.refreshed.append(value)


def service(*values):
    return PurchaseService(Db(*values))


def test_request_purchase_reopens_rejected_record():
    purchase = SimpleNamespace(
        status="rejected",
        request_email="old",
        request_message=None,
        rejection_reason="reason",
    )
    current = service(SimpleNamespace(is_super_admin=False), SimpleNamespace(requires_purchase=True), purchase)
    assert current.request_purchase("tenant", "package", "new", "hello") is purchase
    assert (purchase.status, purchase.request_email, purchase.rejection_reason) == ("pending", "new", None)


def test_approve_purchase_updates_state_and_runs_template_hook():
    purchase = SimpleNamespace(status="pending", tenant_id="tenant", package_id="package", rejection_reason="old")
    current = service(purchase)
    calls = []
    current._try_create_templates = calls.append
    assert current.approve_purchase("purchase", "admin") is purchase
    assert purchase.status == "approved"
    assert purchase.approved_by == "admin"
    assert calls == [purchase]


def test_statistics_counts_purchase_states():
    purchases = [
        SimpleNamespace(status="pending"),
        SimpleNamespace(status="approved"),
        SimpleNamespace(status="approved"),
        SimpleNamespace(status="rejected"),
    ]
    assert service(purchases).get_purchase_statistics() == {
        "total_requests": 4,
        "pending": 1,
        "approved": 2,
        "rejected": 1,
        "approval_rate": 50.0,
    }
