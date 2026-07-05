import asyncio
from types import SimpleNamespace

from services.rate_limiter import PostgreSQLRateLimiter, RateLimitService


def test_rate_limiter_skips_database_when_limit_is_unlimited():
    async def exercise():
        limiter = PostgreSQLRateLimiter()
        limiter._rate_limits = {"tenant-a": 0}
        limiter._cache_update_time = 10**12

        async def fail_if_called(*args):
            raise AssertionError("database check should not run")

        limiter._db_rate_limit_check = fail_if_called

        assert await limiter.is_allowed("tenant-a", db=None) is True

    asyncio.run(exercise())


def test_clear_user_cache_removes_local_counter_and_expires_config():
    limiter = PostgreSQLRateLimiter()
    limiter._local_cache["tenant-a"] = (3, 1.0)
    limiter._cache_update_time = 5.0

    limiter.clear_user_cache("tenant-a")

    assert "tenant-a" not in limiter._local_cache
    assert limiter._cache_update_time == 0.0


def test_monthly_usage_increments_below_limit():
    config = SimpleNamespace(
        monthly_scan_limit=2,
        current_month_usage=0,
        usage_reset_at=None,
        updated_at=None,
    )

    class Db:
        def commit(self):
            pass

        def rollback(self):
            raise AssertionError("rollback should not run")

    service = RateLimitService(Db())
    service._find = lambda tenant_uuid, active_only=False: config

    assert service.check_and_increment_monthly_usage(
        "00000000-0000-0000-0000-000000000001"
    ) == (True, 1, 2)
