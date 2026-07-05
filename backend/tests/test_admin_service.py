import uuid
from types import SimpleNamespace

import services.admin_service as admin_service


class Query:
    def __init__(self, *, first=None, updated=0):
        self._first = first
        self._updated = updated

    def filter(self, *conditions):
        return self

    def first(self):
        return self._first

    def update(self, values):
        return self._updated


class Database:
    def __init__(self, queries):
        self.queries = iter(queries)
        self.added = []
        self.commits = 0

    def query(self, model):
        return next(self.queries)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1


def test_super_admin_accepts_flag_or_configured_email():
    manager = admin_service.ConsoleManager()
    assert manager.is_super_admin(SimpleNamespace(is_super_admin=True, email="other@example.org"))
    assert manager.is_super_admin(SimpleNamespace(is_super_admin=False, email="root@example.org"))
    assert not manager.is_super_admin(SimpleNamespace(is_super_admin=False, email="user@example.org"))


def test_assume_identity_records_switch():
    manager = admin_service.ConsoleManager()
    target_id = uuid.uuid4()
    target = SimpleNamespace(email="target@example.org")
    db = Database([Query(first=target), Query(updated=1)])
    admin = SimpleNamespace(id=uuid.uuid4(), email="root@example.org", is_super_admin=True)
    token = manager.assume_user_identity(db, admin, str(target_id))
    assert token
    assert db.commits == 1
    assert db.added[0].target_tenant_id == target_id
    assert db.added[0].admin_tenant_id == admin.id


def test_assume_identity_rejects_bad_uuid():
    manager = admin_service.ConsoleManager()
    admin = SimpleNamespace(email="root@example.org", is_super_admin=True)
    try:
        manager.assume_user_identity(Database([]), admin, "not-an-id")
    except ValueError as error:
        assert str(error) == "Invalid tenant ID format"
    else:
        raise AssertionError("invalid UUID should be rejected")


def test_resolve_and_release_switch():
    manager = admin_service.ConsoleManager()
    target = SimpleNamespace(id=uuid.uuid4())
    switch = SimpleNamespace(target_tenant_id=target.id)
    db = Database([Query(first=switch), Query(first=target), Query(updated=1)])
    assert manager.resolve_assumed_user(db, "token") is target
    assert manager.release_user_identity(db, "token")
    assert db.commits == 1
