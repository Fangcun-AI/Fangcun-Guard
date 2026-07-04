"""Management-service-specific auth context resolution."""

import uuid
from typing import Optional

from utils.auth import verify_token
from utils.auth_cache import auth_cache
from utils.logger import setup_logger


logger = setup_logger()


class AdminRequestIdentityResolver:
    """Resolve admin console auth context, including impersonation sessions."""

    def __init__(self, *, session_factory, admin_service) -> None:
        self._session_factory = session_factory
        self._admin_service = admin_service

    def should_resolve(self, path: str) -> bool:
        return path.startswith("/api/v1/")

    async def resolve_request_context(self, headers) -> Optional[dict]:
        credential_token = self._extract_credential(headers.get("authorization"))
        if not credential_token:
            return None
        switch_session = headers.get("x-switch-session")
        cache_key = f"{credential_token}:{switch_session or ''}"
        cached_auth = auth_cache.get(cache_key)
        if cached_auth:
            return cached_auth

        db = self._session_factory()
        try:
            auth_context = self._resolve_jwt_context(db, credential_token, switch_session)
            if auth_context is None:
                auth_context = self._resolve_api_key_context(db, credential_token, switch_session)
            if auth_context:
                auth_cache.set(cache_key, auth_context)
            return auth_context
        finally:
            db.close()

    def _extract_credential(self, authorization: Optional[str]) -> Optional[str]:
        if not authorization:
            return None
        if authorization.startswith("Bearer "):
            return authorization.split(" ", 1)[1]
        if authorization.startswith("sk-xxai-"):
            return authorization
        return None

    def _resolve_jwt_context(self, db, credential_token: str, switch_session: Optional[str]) -> Optional[dict]:
        from database.models import Tenant

        try:
            user_data = verify_token(credential_token)
            role = user_data.get("role")
            if role == "admin":
                subject_email = user_data.get("username") or user_data.get("sub")
                admin_user = db.query(Tenant).filter(Tenant.email == subject_email).first()
                if admin_user:
                    return self._build_context(db, "jwt_admin", admin_user, is_super_admin=self._admin_service.is_super_admin(admin_user))

            raw_tenant_id = user_data.get("tenant_id") or user_data.get("sub")
            tenant_uuid = uuid.UUID(raw_tenant_id) if isinstance(raw_tenant_id, str) else None
            user = db.query(Tenant).filter(Tenant.id == tenant_uuid).first() if tenant_uuid else None
            if not user:
                return None

            switched = self._maybe_resolve_switched_user(db, user, switch_session)
            if switched is not None:
                return switched

            return self._build_context(
                db,
                "jwt",
                user,
                is_super_admin=self._admin_service.is_super_admin(user),
            )
        except (ValueError, KeyError, Exception) as exc:
            logger.debug("admin JWT verification failed, falling back to API key: %s", exc)
            return None

    def _resolve_api_key_context(self, db, credential_token: str, switch_session: Optional[str]) -> Optional[dict]:
        from utils.user import find_app_by_key, find_tenant_by_key

        app_data = find_app_by_key(db, credential_token)
        if app_data:
            return {
                "type": "api_key",
                "data": {
                    "tenant_id": app_data["tenant_id"],
                    "email": app_data["tenant_email"],
                    "application_id": app_data["application_id"],
                    "application_name": app_data["application_name"],
                    "api_key": app_data["api_key"],
                    "is_super_admin": False,
                },
            }

        user = find_tenant_by_key(db, credential_token)
        if not user:
            return None

        switched = self._maybe_resolve_switched_user(db, user, switch_session, include_api_key=True, context_type="api_key_switched")
        if switched is not None:
            return switched

        return self._build_context(
            db,
            "api_key_legacy",
            user,
            api_key=user.api_key,
            is_super_admin=self._admin_service.is_super_admin(user),
        )

    def _maybe_resolve_switched_user(self, db, user, switch_session: Optional[str], include_api_key: bool = False, context_type: str = "jwt_switched") -> Optional[dict]:
        if not switch_session or not self._admin_service.is_super_admin(user):
            return None
        switched_user = self._admin_service.resolve_assumed_user(db, switch_session)
        if not switched_user:
            return None

        extra = {
            "original_admin_id": str(user.id),
            "original_admin_email": user.email,
            "switch_session": switch_session,
        }
        if include_api_key:
            extra["api_key"] = switched_user.api_key
        return self._build_context(db, context_type, switched_user, **extra)

    def _build_context(self, db, context_type: str, tenant, **extra) -> dict:
        first_app = self._load_first_active_application(db, tenant.id)
        data = {
            "tenant_id": str(tenant.id),
            "email": tenant.email,
            "application_id": str(first_app.id) if first_app else None,
            "application_name": first_app.name if first_app else None,
        }
        data.update(extra)
        return {"type": context_type, "data": data}

    def _load_first_active_application(self, db, tenant_id):
        from database.models import Application

        return (
            db.query(Application)
            .filter(Application.tenant_id == tenant_id, Application.is_active == True)
            .first()
        )
