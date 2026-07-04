"""Subscription and quota HTTP adapters shared by the edge services."""

from collections.abc import Callable  # fcg-rewrite
from typing import Any, Optional  # fcg-rewrite
import uuid  # fcg-rewrite

from fastapi import APIRouter, Depends, HTTPException, Request  # fcg-rewrite
from pydantic import BaseModel  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.connection import get_admin_db  # fcg-rewrite
from database.models import Tenant  # fcg-rewrite
from services.admin_service import admin_service  # fcg-rewrite
from services.billing_service import billing_service  # fcg-rewrite
from utils.auth import verify_token  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite


logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Billing"])  # fcg-rewrite


class UsageBreakdown(BaseModel):  # fcg-rewrite
    guardrails_proxy: int = 0  # fcg-rewrite
    direct_model_access: int = 0  # fcg-rewrite


class SubscriptionResponse(BaseModel):  # fcg-rewrite
    id: str
    tenant_id: str  # fcg-rewrite
    subscription_type: str  # fcg-rewrite
    subscription_tier: int = 0  # fcg-rewrite
    monthly_quota: int  # fcg-rewrite
    current_month_usage: int  # fcg-rewrite
    usage_reset_at: str  # fcg-rewrite
    usage_percentage: float  # fcg-rewrite
    plan_name: str  # fcg-rewrite
    usage_breakdown: Optional[UsageBreakdown] = None  # fcg-rewrite
    billing_period_start: Optional[str] = None  # fcg-rewrite
    billing_period_end: Optional[str] = None  # fcg-rewrite
    purchased_quota: int = 0  # fcg-rewrite
    purchased_quota_expires_at: Optional[str] = None  # fcg-rewrite


class UpdateSubscriptionRequest(BaseModel):  # fcg-rewrite
    subscription_type: str  # fcg-rewrite


def _load_tenant_by_id(db: Session, tenant_id: object) -> Optional[Tenant]:  # fcg-rewrite
    try:
        return db.query(Tenant).filter(Tenant.id == uuid.UUID(str(tenant_id))).first()  # fcg-rewrite
    except (TypeError, ValueError, AttributeError):  # fcg-rewrite
        return None  # fcg-rewrite


def get_current_user(request: Request, db: Session) -> Tenant:  # fcg-rewrite
    context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    data = context.get("data", {}) if isinstance(context, dict) else {}  # fcg-rewrite
    tenant = _load_tenant_by_id(db, data.get("tenant_id"))  # fcg-rewrite
    if tenant:  # fcg-rewrite
        return tenant  # fcg-rewrite

    authorization = request.headers.get("Authorization", "")  # fcg-rewrite
    if not authorization.startswith("Bearer "):  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite
    try:
        email = verify_token(authorization.split(" ", 1)[1]).get("sub")  # fcg-rewrite
        tenant = db.query(Tenant).filter(Tenant.email == email).first() if email else None  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.warning("billing token verification failed: %s", exc)  # fcg-rewrite
        tenant = None  # fcg-rewrite
    if not tenant:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Invalid credentials")  # fcg-rewrite
    if not tenant.is_active or not tenant.is_verified:  # fcg-rewrite
        raise HTTPException(status_code=403, detail="Tenant account not active")  # fcg-rewrite
    return tenant  # fcg-rewrite


def _execute(label: str, operation: Callable[[], Any], *, value_error_status: int = 500):  # fcg-rewrite
    try:
        return operation()  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except ValueError as exc:  # fcg-rewrite
        if value_error_status != 500:  # fcg-rewrite
            raise HTTPException(status_code=value_error_status, detail=str(exc)) from exc  # fcg-rewrite
        logger.error("%s: %s", label, exc)  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        logger.error("%s: %s", label, exc)  # fcg-rewrite
    raise HTTPException(status_code=500, detail="Internal server error")  # fcg-rewrite


def _subscription_for(request: Request, db: Session) -> dict:  # fcg-rewrite
    result = billing_service.get_subscription_with_usage(str(get_current_user(request, db).id), db)  # fcg-rewrite
    if not result:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Subscription not found. Please contact support.")  # fcg-rewrite
    return result  # fcg-rewrite


def _require_super_admin(request: Request, db: Session) -> Tenant:  # fcg-rewrite
    tenant = get_current_user(request, db)  # fcg-rewrite
    if not admin_service.is_super_admin(tenant):  # fcg-rewrite
        raise HTTPException(status_code=403, detail="Access denied: Super admin required")  # fcg-rewrite
    return tenant  # fcg-rewrite


def _success(data: Any, message: Optional[str] = None, **metadata) -> dict:  # fcg-rewrite
    payload = {"status": "success", "data": data, **metadata}  # fcg-rewrite
    if message:  # fcg-rewrite
        payload["message"] = message  # fcg-rewrite
    return payload  # fcg-rewrite


@router.get("/api/v1/billing/subscription", response_model=SubscriptionResponse)  # fcg-rewrite
async def get_my_subscription(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return _execute("failed to get subscription", lambda: SubscriptionResponse(**_subscription_for(request, db)))  # fcg-rewrite


@router.get("/api/v1/billing/usage")  # fcg-rewrite
async def get_my_usage(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    def read_usage():  # fcg-rewrite
        info = _subscription_for(request, db)  # fcg-rewrite
        keys = ("current_month_usage", "monthly_quota", "usage_percentage", "usage_reset_at", "subscription_type", "plan_name")  # fcg-rewrite
        usage = {key: info[key] for key in keys}  # fcg-rewrite
        usage["remaining"] = info["monthly_quota"] - info["current_month_usage"]  # fcg-rewrite
        return _success(usage)  # fcg-rewrite

    return _execute("failed to get usage", read_usage)  # fcg-rewrite


@router.get("/api/v1/admin/billing/subscriptions")  # fcg-rewrite
async def list_all_subscriptions(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    skip: int = 0,  # fcg-rewrite
    limit: int = 100,  # fcg-rewrite
    search: Optional[str] = None,  # fcg-rewrite
    subscription_type: Optional[str] = None,  # fcg-rewrite
    sort_by: Optional[str] = "current_month_usage",  # fcg-rewrite
    sort_order: Optional[str] = "desc",  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    def read_all():  # fcg-rewrite
        _require_super_admin(request, db)  # fcg-rewrite
        rows, total = billing_service.list_subscriptions(db, skip, limit, search, subscription_type, sort_by, sort_order)  # fcg-rewrite
        return _success(rows, total=total, skip=skip, limit=limit)  # fcg-rewrite

    return _execute("failed to list subscriptions", read_all)  # fcg-rewrite


@router.put("/api/v1/admin/billing/subscriptions/{tenant_id}")  # fcg-rewrite
async def update_tenant_subscription(  # fcg-rewrite
    tenant_id: str,  # fcg-rewrite
    request_data: UpdateSubscriptionRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    def update():  # fcg-rewrite
        _require_super_admin(request, db)  # fcg-rewrite
        plan = request_data.subscription_type  # fcg-rewrite
        if plan not in {"free", "subscribed"}:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Invalid subscription type. Must be 'free' or 'subscribed'")  # fcg-rewrite
        subscription = billing_service.update_subscription_type(tenant_id, plan, db)  # fcg-rewrite
        return _success(  # fcg-rewrite
            {"tenant_id": str(subscription.tenant_id), "subscription_type": subscription.subscription_type, "monthly_quota": subscription.monthly_quota},  # fcg-rewrite
            f"Subscription updated to {plan}",  # fcg-rewrite
        )

    return _execute("failed to update subscription", update, value_error_status=404)  # fcg-rewrite


@router.post("/api/v1/admin/billing/subscriptions/{tenant_id}/reset-quota")  # fcg-rewrite
async def reset_tenant_quota(tenant_id: str, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    def reset():  # fcg-rewrite
        _require_super_admin(request, db)  # fcg-rewrite
        subscription = billing_service.reset_monthly_quota(tenant_id, db)  # fcg-rewrite
        return _success(  # fcg-rewrite
            {
                "tenant_id": str(subscription.tenant_id),  # fcg-rewrite
                "current_month_usage": subscription.current_month_usage,  # fcg-rewrite
                "monthly_quota": subscription.monthly_quota,  # fcg-rewrite
                "usage_reset_at": subscription.usage_reset_at.isoformat(),  # fcg-rewrite
            },
            f"Quota reset for tenant {tenant_id}",  # fcg-rewrite
        )

    return _execute("failed to reset quota", reset, value_error_status=404)  # fcg-rewrite


@router.post("/api/v1/admin/billing/reset-all-quotas")  # fcg-rewrite
async def reset_all_quotas(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    def reset():  # fcg-rewrite
        _require_super_admin(request, db)  # fcg-rewrite
        count = billing_service.reset_all_quotas(db)  # fcg-rewrite
        return _success({"reset_count": count}, f"Reset quotas for {count} tenants")  # fcg-rewrite

    return _execute("failed to reset all quotas", reset)  # fcg-rewrite
