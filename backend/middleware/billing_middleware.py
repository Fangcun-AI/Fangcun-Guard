"""Monthly SaaS quota enforcement for guarded model traffic."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import settings
from database.connection import get_db_session
from services.billing_service import billing_service
from utils.logger import setup_logger

logger = setup_logger()


class BillingMiddleware(BaseHTTPMiddleware):
    protected_paths = ("/v1/guardrails", "/v1/chat/completions")

    async def dispatch(self, request: Request, call_next):
        context = getattr(request.state, "auth_context", None)
        protected = any(request.url.path.startswith(path) for path in self.protected_paths)
        if settings.is_enterprise_mode or not protected or not context:
            return await call_next(request)
        tenant_id = context["data"].get("tenant_id")
        if not tenant_id:
            return await call_next(request)
        db = get_db_session()
        try:
            allowed, message = billing_service.check_and_increment_usage(
                str(tenant_id), db
            )
            if not allowed:
                logger.warning(f"Billing quota exceeded for tenant {tenant_id}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "message": message
                            or "Monthly quota exceeded. Please upgrade your plan or wait for quota reset.",
                            "type": "quota_exceeded",
                            "code": 429,
                        }
                    },
                    headers={"Retry-After": "86400"},
                )
        except Exception as exc:
            logger.error(f"Billing check failed for tenant {tenant_id}: {exc}")
        finally:
            db.close()
        return await call_next(request)
