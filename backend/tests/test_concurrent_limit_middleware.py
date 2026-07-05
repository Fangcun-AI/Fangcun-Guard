import asyncio
from types import SimpleNamespace

from middleware.concurrent_limit_middleware import ConcurrentLimitMiddleware


def setup_function():
    ConcurrentLimitMiddleware._semaphores.clear()
    ConcurrentLimitMiddleware._stats.clear()


def build_middleware(limit=1):
    return ConcurrentLimitMiddleware(lambda *_args: None, "test", limit)


def test_dispatch_adds_headers_and_releases_slot():
    async def exercise():
        middleware = build_middleware()
        response = SimpleNamespace(headers={})
        result = await middleware.dispatch(
            SimpleNamespace(url=SimpleNamespace(path="/scan")),
            lambda _request: asyncio.sleep(0, result=response),
        )
        assert result.headers["X-Service-Type"] == "test"
        assert middleware.get_stats("test")["current_requests"] == 0

    asyncio.run(exercise())


def test_dispatch_rejects_when_slot_is_occupied():
    async def exercise():
        middleware = build_middleware()
        semaphore = middleware._semaphores["test"]
        await semaphore.acquire()
        response = await middleware.dispatch(
            SimpleNamespace(url=SimpleNamespace(path="/scan")),
            lambda _request: None,
        )
        assert response.status_code == 429
        assert middleware.get_stats("test")["rejected_requests"] == 1

    asyncio.run(exercise())
