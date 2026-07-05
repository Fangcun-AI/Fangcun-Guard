"""Legacy tenant response-template lookup helpers."""

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from database.models import ResponseTemplate


def create_user_default_templates(db: Session, tenant_id: uuid.UUID) -> int:
    try:
        existing = db.query(ResponseTemplate).filter_by(tenant_id=tenant_id).count()
        if existing:
            return existing
        defaults = db.query(ResponseTemplate).filter(
            ResponseTemplate.tenant_id.is_(None),
            ResponseTemplate.is_default == True,
        ).all()
        for template in defaults:
            db.add(
                ResponseTemplate(
                    tenant_id=tenant_id,
                    category=template.category,
                    risk_level=template.risk_level,
                    template_content=template.template_content,
                    is_default=template.is_default,
                    is_active=template.is_active,
                )
            )
        db.commit()
        return len(defaults)
    except Exception:
        db.rollback()
        raise


def _active_template(db: Session, tenant_id, category: str, risk_level=None):
    conditions = [
        ResponseTemplate.tenant_id == tenant_id,
        ResponseTemplate.category == category,
        ResponseTemplate.is_active == True,
    ]
    if risk_level is not None:
        conditions.append(ResponseTemplate.risk_level == risk_level)
    return db.query(ResponseTemplate).filter(*conditions).first()


def get_user_template(
    db: Session,
    tenant_id: uuid.UUID,
    category: str,
    risk_level: str,
) -> Optional[ResponseTemplate]:
    return _active_template(db, tenant_id, category, risk_level) or _active_template(
        db, None, category, risk_level
    )


def get_default_template(
    db: Session,
    tenant_id: Optional[uuid.UUID] = None,
) -> Optional[ResponseTemplate]:
    return (
        _active_template(db, tenant_id, "default") if tenant_id else None
    ) or _active_template(db, None, "default")
