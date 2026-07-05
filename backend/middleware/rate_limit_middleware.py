"""Per-tenant request-rate enforcement for detection traffic."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from database.connection import get_db_session
from services.rate_limiter import rate_limiter
from utils.logger import setup_logger

logger = setup_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    protected_paths = ("/v1/guardrails",)

    async def dispatch(self, request: Request, call_next):
        if not self._tenant_request(request):
            return await call_next(request)
        tenant_id = request.state.auth_context["data"].get("tenant_id")
        if not tenant_id:
            return await call_next(request)
        db = get_db_session()
        try:
            if not await rate_limiter.is_allowed(str(tenant_id), db):
                logger.warning(f"Rate limit exceeded for tenant {tenant_id}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "message": "Rate limit exceeded. Too many requests.",
                            "type": "rate_limit_exceeded",
                            "code": 429,
                        }
                    },
                    headers={"Retry-After": "1"},
                )
        except Exception as exc:
            logger.error(f"Rate limit check failed: {exc}")
        finally:
            db.close()
        return await call_next(request)

    def _tenant_request(self, request: Request) -> bool:
        protected = any(request.url.path.startswith(path) for path in self.protected_paths)
        online_test = request.headers.get("X-Online-Test") or request.headers.get("x-online-test")
        return protected and not online_test and bool(
            getattr(request.state, "auth_context", None)
        )
