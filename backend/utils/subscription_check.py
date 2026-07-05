"""Subscription feature gates used by SaaS deployments."""

from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from database.models import Tenant, TenantSubscription
from utils.logger import setup_logger

logger = setup_logger()


class SubscriptionFeature:
    GENAI_RECOGNITION = "genai_recognition"
    GENAI_CODE_ANONYMIZATION = "genai_code_anonymization"
    NATURAL_LANGUAGE_DESC = "natural_language_desc"
    FORMAT_DETECTION = "format_detection"
    SMART_SEGMENTATION = "smart_segmentation"
    CUSTOM_SCANNERS = "custom_scanners"


FEATURE_DESCRIPTIONS = {
    SubscriptionFeature.GENAI_RECOGNITION: {"en": "GenAI entity recognition", "zh": "AI 智能识别"},
    SubscriptionFeature.GENAI_CODE_ANONYMIZATION: {"en": "GenAI code-based anonymization", "zh": "AI 代码脱敏"},
    SubscriptionFeature.NATURAL_LANGUAGE_DESC: {"en": "Natural language anonymization description", "zh": "自然语言脱敏描述"},
    SubscriptionFeature.FORMAT_DETECTION: {"en": "Auto format detection", "zh": "自动格式检测"},
    SubscriptionFeature.SMART_SEGMENTATION: {"en": "Smart content segmentation", "zh": "智能内容分段"},
    SubscriptionFeature.CUSTOM_SCANNERS: {"en": "Custom scanners", "zh": "自定义扫描器"},
}
_FEATURES = tuple(FEATURE_DESCRIPTIONS)


def is_enterprise_mode() -> bool:
    return settings.is_enterprise_mode


def _feature_name(feature: str, language: str) -> str:
    return FEATURE_DESCRIPTIONS.get(feature, {}).get(language, feature)


def _subscription_is_active(subscription) -> bool:
    if not subscription or subscription.subscription_type != "subscribed":
        return False
    expiry = subscription.subscription_expires_at
    return not expiry or datetime.now(timezone.utc) <= expiry


def _subscription_is_expired(subscription) -> bool:
    return bool(
        subscription
        and subscription.subscription_type == "subscribed"
        and subscription.subscription_expires_at
        and datetime.now(timezone.utc) > subscription.subscription_expires_at
    )


def _tenant_access(db: Session, tenant_uuid: UUID) -> tuple[bool, object]:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()
    if tenant and getattr(tenant, "is_super_admin", False):
        return True, None
    subscription = db.query(TenantSubscription).filter(
        TenantSubscription.tenant_id == tenant_uuid
    ).first()
    return _subscription_is_active(subscription), subscription


def check_subscription_for_feature(
    tenant_id: str,
    db: Session,
    feature: str,
    language: str = "en",
) -> Tuple[bool, Optional[str]]:
    if is_enterprise_mode():
        return True, None
    try:
        allowed, subscription = _tenant_access(db, UUID(tenant_id))
        if allowed:
            return True, None
        name = _feature_name(feature, language)
        expired = _subscription_is_expired(subscription)
        if language == "zh":
            message = (
                f"您的订阅已过期。「{name}」是高级功能，请续费后使用。"
                if expired
                else f"「{name}」是高级功能，请升级到订阅计划后使用。"
            )
        else:
            message = (
                f"Your subscription has expired. '{name}' is a premium feature. "
                "Please renew your subscription."
                if expired
                else f"'{name}' is a premium feature. Please upgrade to a subscribed "
                "plan to access this feature."
            )
        logger.info(f"Feature '{feature}' denied for tenant {tenant_id}")
        return False, message
    except Exception as exc:
        logger.error(f"Subscription check failed for tenant {tenant_id}: {exc}")
        return True, None


def require_subscription_for_feature(
    tenant_id: str,
    db: Session,
    feature: str,
    language: str = "en",
) -> None:
    allowed, message = check_subscription_for_feature(tenant_id, db, feature, language)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def get_feature_availability(tenant_id: str, db: Session) -> dict:
    enterprise = is_enterprise_mode()
    result = {"is_enterprise": enterprise, "is_subscribed": enterprise, "features": {}}
    if enterprise:
        result["features"] = dict.fromkeys(_FEATURES, True)
        return result
    try:
        allowed, _ = _tenant_access(db, UUID(tenant_id))
        result["is_subscribed"] = allowed
        result["features"] = dict.fromkeys(_FEATURES, allowed)
    except Exception as exc:
        logger.error(f"Failed to get feature availability for tenant {tenant_id}: {exc}")
        result["features"] = dict.fromkeys(_FEATURES, True)
    return result
