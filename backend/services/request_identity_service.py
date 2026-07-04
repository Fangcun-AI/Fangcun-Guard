"""Shared request identity resolution for FastAPI edge services."""

from dataclasses import dataclass
from typing import Callable, Mapping, Optional
import uuid

from utils.auth import verify_token
from utils.auth_cache import auth_cache
from utils.logger import setup_logger
from utils.request_headers import read_external_app_id
from utils.user import ensure_app_for_external_id, find_app_by_key, find_tenant_by_key


logger = setup_logger()


@dataclass(frozen=True)
class RequestIdentityPolicy:
    """Service-specific rules for extracting and resolving caller identity."""

    route_prefixes: tuple[str, ...]
    allow_direct_api_keys: bool = False
    require_tenant_record_for_jwt: bool = False

    def matches(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.route_prefixes)

    def extract_credential(self, authorization: Optional[str]) -> Optional[str]:
        if not authorization:
            return None
        if authorization.startswith("Bearer "):
            return authorization.split(" ", 1)[1]
        if self.allow_direct_api_keys and authorization.startswith("sk-xxai-"):
            return authorization
        return None


class RequestIdentityResolver:
    """Resolve auth context from JWTs or tenant/application API keys."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], object],
        policy: RequestIdentityPolicy,
        service_name: str,
    ) -> None:
        self._session_factory = session_factory
        self._policy = policy
        self._service_name = service_name

    def should_resolve(self, path: str) -> bool:
        return self._policy.matches(path)

    async def resolve_request_context(self, headers: Mapping[str, str]) -> Optional[dict]:
        credential_token = self._policy.extract_credential(headers.get("authorization"))
        if not credential_token:
            return None
        return self._resolve_context(credential_token, headers)

    def _resolve_context(self, credential_token: str, headers: Mapping[str, str]) -> Optional[dict]:
        external_app_id = read_external_app_id(headers)
        cache_key = None if external_app_id else credential_token

        if cache_key:
            cached_context = auth_cache.get(cache_key)
            if cached_context:
                return cached_context

        db = self._session_factory()
        try:
            resolved_context = self._resolve_jwt_context(db, credential_token)
            if resolved_context is None:
                resolved_context = self._resolve_api_key_context(db, credential_token, external_app_id)
        except Exception as exc:
            logger.warning("%s identity resolution failed: %s", self._service_name, exc)
            return None
        finally:
            db.close()

        if resolved_context and cache_key:
            auth_cache.set(cache_key, resolved_context)

        return resolved_context

    def _resolve_jwt_context(self, db, credential_token: str) -> Optional[dict]:
        try:
            user_data = verify_token(credential_token)
            raw_tenant_id = user_data.get("tenant_id") or user_data.get("sub")
            if not isinstance(raw_tenant_id, str):
                return None

            tenant_uuid = uuid.UUID(raw_tenant_id)
            tenant_record = self._load_tenant_if_required(db, tenant_uuid)
            if self._policy.require_tenant_record_for_jwt and tenant_record is None:
                return None

            first_app = self._load_first_active_application(db, tenant_uuid)
            return {
                "type": "jwt",
                "data": {
                    "tenant_id": str(tenant_record.id) if tenant_record is not None else raw_tenant_id,
                    "email": tenant_record.email if tenant_record is not None else user_data.get("email", "unknown"),
                    "application_id": str(first_app.id) if first_app else None,
                    "application_name": first_app.name if first_app else None,
                },
            }
        except (ValueError, KeyError, Exception) as jwt_err:
            logger.debug("%s JWT verification failed, falling back to API key: %s", self._service_name, jwt_err)
            return None

    def _resolve_api_key_context(
        self,
        db,
        credential_token: str,
        external_app_id: Optional[str],
    ) -> Optional[dict]:
        if external_app_id:
            tenant = find_tenant_by_key(db, credential_token)
            if not tenant:
                return None

            app_info = ensure_app_for_external_id(db, str(tenant.id), external_app_id)
            if not app_info:
                return None

            return {
                "type": "tenant_api_key_with_consumer",
                "data": {
                    "tenant_id": str(tenant.id),
                    "email": tenant.email,
                    "api_key": tenant.api_key,
                    "application_id": app_info["application_id"],
                    "application_name": app_info["application_name"],
                    "is_auto_discovered": app_info["is_new"],
                    "external_app_id": external_app_id,
                },
            }

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
                },
            }

        tenant = find_tenant_by_key(db, credential_token)
        if not tenant:
            return None

        first_app = self._load_first_active_application(db, tenant.id)
        return {
            "type": "api_key_legacy",
            "data": {
                "tenant_id": str(tenant.id),
                "email": tenant.email,
                "api_key": tenant.api_key,
                "application_id": str(first_app.id) if first_app else None,
                "application_name": first_app.name if first_app else None,
            },
        }

    def _load_first_active_application(self, db, tenant_id):
        from database.models import Application

        return (
            db.query(Application)
            .filter(Application.tenant_id == tenant_id, Application.is_active == True)
            .first()
        )

    def _load_tenant_if_required(self, db, tenant_id):
        if not self._policy.require_tenant_record_for_jwt:
            return None

        from database.models import Tenant

        return db.query(Tenant).filter(Tenant.id == tenant_id).first()
