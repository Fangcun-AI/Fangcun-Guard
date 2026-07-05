"""Administrative tenant bootstrap and identity-switch operations."""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from passlib.context import CryptContext
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from config import settings
from database.models import DetectionResult, Tenant, TenantSwitch
from utils.logger import setup_logger
from utils.user import new_api_key

logger = setup_logger()


class ConsoleManager:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def _create_default_templates(self, db: Session, tenant: Tenant) -> None:
        try:
            from services.template_service import create_user_default_templates

            created = create_user_default_templates(db, tenant.id)
            if created:
                logger.info("Created %s default templates for %s", created, tenant.email)
        except Exception as error:
            logger.error("Failed to create default templates for %s: %s", tenant.email, error)

    def seed_super_admin(self, db: Session) -> Tenant:
        """Create the configured administrator or bring its credentials up to date."""
        try:
            admin = (
                db.query(Tenant)
                .filter(
                    Tenant.email == settings.super_admin_username,
                    Tenant.is_super_admin == True,
                )
                .first()
            )
            if not admin:
                admin = Tenant(
                    email=settings.super_admin_username,
                    password_hash=self.pwd_context.hash(settings.super_admin_password),
                    is_active=True,
                    is_verified=True,
                    is_super_admin=True,
                    api_key=self._generate_api_key(),
                )
                db.add(admin)
                db.commit()
                db.refresh(admin)
                self._create_default_templates(db, admin)
                logger.info("Super admin created: %s", admin.email)
                return admin

            changed = False
            try:
                password_matches = self.pwd_context.verify(
                    settings.super_admin_password, admin.password_hash
                )
            except Exception:
                password_matches = False
            if not password_matches:
                admin.password_hash = self.pwd_context.hash(settings.super_admin_password)
                changed = True
            for field in ("is_active", "is_verified", "is_super_admin"):
                if not getattr(admin, field):
                    setattr(admin, field, True)
                    changed = True
            if changed:
                db.commit()
                db.refresh(admin)
            self._create_default_templates(db, admin)
            return admin
        except Exception:
            db.rollback()
            logger.exception("Failed to seed super admin")
            raise

    def _generate_api_key(self) -> str:
        return new_api_key()

    def is_super_admin(self, tenant: Tenant) -> bool:
        return bool(
            tenant
            and (
                getattr(tenant, "is_super_admin", False)
                or tenant.email == settings.super_admin_username
            )
        )

    def _require_super_admin(self, tenant: Tenant, error: str) -> None:
        if not self.is_super_admin(tenant):
            raise PermissionError(error)

    def get_all_users(
        self,
        db: Session,
        admin_tenant: Tenant,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], int]:
        self._require_super_admin(admin_tenant, "Only super admin can access all tenants")
        query = db.query(
            Tenant,
            func.count(DetectionResult.id).label("detection_count"),
            func.max(DetectionResult.created_at).label("last_activity"),
        ).outerjoin(DetectionResult, Tenant.id == DetectionResult.tenant_id)
        if search:
            from sqlalchemy import String, cast

            wildcard = f"%{search}%"
            query = query.filter(
                Tenant.email.ilike(wildcard) | cast(Tenant.id, String).ilike(wildcard)
            )
        query = query.group_by(Tenant.id)
        total = query.count()
        column = {
            "detection_count": "detection_count",
            "last_activity": "last_activity",
        }.get(sort_by, Tenant.created_at)
        order = desc(column) if sort_order == "desc" else asc(column)
        rows = query.order_by(order).offset(skip).limit(limit).all()
        return [self._serialize_user(*row) for row in rows], total

    def _serialize_user(self, tenant: Tenant, detection_count: int, last_activity) -> dict:
        return {
            "id": str(tenant.id),
            "email": tenant.email,
            "is_active": tenant.is_active,
            "is_super_admin": self.is_super_admin(tenant),
            "is_verified": tenant.is_verified,
            "api_key": tenant.api_key,
            "detection_count": detection_count,
            "last_activity": last_activity.isoformat() if last_activity else None,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
        }

    def assume_user_identity(
        self, db: Session, admin_tenant: Tenant, target_tenant_id: Union[str, uuid.UUID]
    ) -> str:
        self._require_super_admin(admin_tenant, "Only super admin can switch tenant view")
        try:
            target_id = (
                uuid.UUID(target_tenant_id)
                if isinstance(target_tenant_id, str)
                else target_tenant_id
            )
        except ValueError as error:
            raise ValueError("Invalid tenant ID format") from error
        target = (
            db.query(Tenant)
            .filter(Tenant.id == target_id, Tenant.is_active == True)
            .first()
        )
        if not target:
            raise ValueError("Target tenant not found or inactive")
        token = secrets.token_urlsafe(64)
        db.query(TenantSwitch).filter(
            TenantSwitch.admin_tenant_id == admin_tenant.id,
            TenantSwitch.is_active == True,
        ).update({"is_active": False})
        db.add(
            TenantSwitch(
                admin_tenant_id=admin_tenant.id,
                target_tenant_id=target_id,
                session_token=token,
                expires_at=datetime.now() + timedelta(hours=2),
            )
        )
        db.commit()
        logger.info("Super admin %s switched to tenant %s", admin_tenant.email, target.email)
        return token

    def _find_switch(self, db: Session, token: str, *, require_unexpired: bool = False):
        conditions = [TenantSwitch.session_token == token, TenantSwitch.is_active == True]
        if require_unexpired:
            conditions.append(TenantSwitch.expires_at > datetime.now())
        return db.query(TenantSwitch).filter(*conditions).first()

    def resolve_assumed_user(self, db: Session, session_token: str) -> Optional[Tenant]:
        switch = self._find_switch(db, session_token, require_unexpired=True)
        return db.query(Tenant).filter(Tenant.id == switch.target_tenant_id).first() if switch else None

    def release_user_identity(self, db: Session, session_token: str) -> bool:
        changed = db.query(TenantSwitch).filter(
            TenantSwitch.session_token == session_token,
            TenantSwitch.is_active == True,
        ).update({"is_active": False})
        db.commit()
        return changed > 0

    def resolve_admin_from_switch(self, db: Session, session_token: str) -> Optional[Tenant]:
        switch = self._find_switch(db, session_token)
        return db.query(Tenant).filter(Tenant.id == switch.admin_tenant_id).first() if switch else None


admin_service = ConsoleManager()
