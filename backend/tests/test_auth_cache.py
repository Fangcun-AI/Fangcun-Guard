from unittest.mock import patch

from utils.auth_cache import AuthSessionStore


def test_auth_cache_expires_entries_using_monotonic_time():
    store = AuthSessionStore(ttl=5)
    with patch("utils.auth_cache.time.monotonic", side_effect=[10, 12, 16]):
        store.set("token", {"data": {"tenant_id": "tenant-a"}})
        assert store.get("token") == {"data": {"tenant_id": "tenant-a"}}
        assert store.get("token") is None


def test_auth_cache_can_invalidate_a_tenant_scope():
    store = AuthSessionStore()
    store.set("token-a", {"data": {"tenant_id": "tenant-a"}})
    store.set("token-b", {"data": {"tenant_id": "tenant-b"}})

    store.invalidate_by_tenant("tenant-a")

    assert store.get("token-a") is None
    assert store.get("token-b") == {"data": {"tenant_id": "tenant-b"}}
