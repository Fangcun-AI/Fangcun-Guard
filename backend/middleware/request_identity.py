"""Shared middleware for attaching auth context to incoming requests."""

from starlette.middleware.base import BaseHTTPMiddleware

from services.request_identity_service import RequestIdentityResolver


class RequestIdentityMiddleware(BaseHTTPMiddleware):
    """Attach the resolved auth context to ``request.state`` when applicable."""

    def __init__(self, app, *, resolver: RequestIdentityResolver):
        super().__init__(app)
        self._resolver = resolver

    async def dispatch(self, request, call_next):
        if self._resolver.should_resolve(request.url.path):
            request.state.auth_context = await self._resolver.resolve_request_context(request.headers)
        return await call_next(request)
