import asyncio
from types import SimpleNamespace

import middleware.billing_middleware as billing
import middleware.rate_limit_middleware as rate


class Db:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def request(path):
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        headers={},
        state=SimpleNamespace(auth_context={"data": {"tenant_id": "tenant"}}),
    )


def test_rate_limit_rejection_closes_session():
    async def exercise():
        db = Db()
        rate.get_db_session = lambda: db

        async def denied(*_args):
            return False

        rate.rate_limiter = SimpleNamespace(is_allowed=denied)
        response = await rate.RateLimitMiddleware(lambda: None).dispatch(
            request("/v1/guardrails"), lambda _request: None
        )
        assert response.status_code == 429
        assert db.closed

    asyncio.run(exercise())


def test_billing_enterprise_mode_skips_quota_check():
    async def exercise():
        billing.settings = SimpleNamespace(is_enterprise_mode=True)
        result = await billing.BillingMiddleware(lambda: None).dispatch(
            request("/v1/chat/completions"),
            lambda _request: asyncio.sleep(0, result="allowed"),
        )
        assert result == "allowed"

    asyncio.run(exercise())
