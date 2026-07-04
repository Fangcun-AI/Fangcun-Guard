"""Super-admin tenant management endpoints."""

from datetime import datetime, timedelta  # fcg-rewrite
from typing import Optional  # fcg-rewrite
import uuid  # fcg-rewrite

from fastapi import APIRouter, Depends, Header, HTTPException, Request  # fcg-rewrite
from pydantic import BaseModel, EmailStr  # fcg-rewrite
from sqlalchemy import desc, func  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.connection import get_admin_db  # fcg-rewrite
from database.models import (  # fcg-rewrite
    Blacklist,  # fcg-rewrite
    DataSecurityEntityType,  # fcg-rewrite
    DetectionResult,  # fcg-rewrite
    KnowledgeBase,  # fcg-rewrite
    OnlineTestModelSelection,  # fcg-rewrite
    ProxyModelConfig,  # fcg-rewrite
    ProxyRequestLog,  # fcg-rewrite
    ResponseTemplate,  # fcg-rewrite
    RiskTypeConfig,  # fcg-rewrite
    Tenant,
    TenantRateLimit,  # fcg-rewrite
    TenantRateLimitCounter,  # fcg-rewrite
    TenantSubscription,  # fcg-rewrite
    TenantSwitch,  # fcg-rewrite
    TestModelConfig,  # fcg-rewrite
    Whitelist,  # fcg-rewrite
)
from services.admin_service import admin_service  # fcg-rewrite
from services.rate_limiter import RateLimitService  # fcg-rewrite
from utils.auth import generate_api_key, get_password_hash  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Admin"])  # fcg-rewrite


def _uuid(value: str) -> uuid.UUID:  # fcg-rewrite
    try:
        return uuid.UUID(value)  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid tenant ID format") from exc  # fcg-rewrite


def _find_tenant(db: Session, tenant_id: str) -> Tenant:  # fcg-rewrite
    tenant = db.query(Tenant).filter(Tenant.id == _uuid(tenant_id)).first()  # fcg-rewrite
    if not tenant:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Tenant not found")  # fcg-rewrite
    return tenant  # fcg-rewrite


def get_current_user(request: Request, db: Optional[Session] = None) -> Tenant:  # fcg-rewrite
    """Return the original administrator while a view-switch is active."""
    context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    if not context:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite
    data = context["data"]  # fcg-rewrite
    tenant_id = data.get("original_admin_id") or data.get("tenant_id")  # fcg-rewrite
    if not tenant_id:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Invalid tenant context")  # fcg-rewrite

    owned_db = db is None  # fcg-rewrite
    db = db or next(get_admin_db())  # fcg-rewrite
    try:
        try:
            tenant_uuid = uuid.UUID(str(tenant_id))  # fcg-rewrite
        except ValueError as exc:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="Invalid tenant context") from exc  # fcg-rewrite
        tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()  # fcg-rewrite
        if not tenant:  # fcg-rewrite
            raise HTTPException(status_code=401, detail="Tenant not found")  # fcg-rewrite
        return tenant  # fcg-rewrite
    finally:  # fcg-rewrite
        if owned_db:  # fcg-rewrite
            db.close()  # fcg-rewrite


def _require_admin(request: Request, db: Session) -> Tenant:  # fcg-rewrite
    tenant = get_current_user(request, db)  # fcg-rewrite
    if not admin_service.is_super_admin(tenant):  # fcg-rewrite
        raise HTTPException(status_code=403, detail="Access denied: Super admin required")  # fcg-rewrite
    return tenant  # fcg-rewrite


def _server_error(label: str, exc: Exception, db: Optional[Session] = None):  # fcg-rewrite
    if db:
        db.rollback()  # fcg-rewrite
    logger.error("%s error: %s", label, exc)  # fcg-rewrite
    raise HTTPException(status_code=500, detail="Internal server error") from exc  # fcg-rewrite


@router.get("/admin/stats")  # fcg-rewrite
async def get_admin_stats(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        _require_admin(request, db)  # fcg-rewrite
        rows = db.query(  # fcg-rewrite
            Tenant.id.label("tenant_id"),  # fcg-rewrite
            Tenant.email.label("email"),  # fcg-rewrite
            func.count(DetectionResult.id).label("detection_count"),  # fcg-rewrite
        ).outerjoin(DetectionResult, Tenant.id == DetectionResult.tenant_id).group_by(  # fcg-rewrite
            Tenant.id, Tenant.email  # fcg-rewrite
        ).all()
        return {  # fcg-rewrite
            "status": "success",  # fcg-rewrite
            "data": {  # fcg-rewrite
                "total_users": db.query(Tenant).count(),  # fcg-rewrite
                "total_detections": db.query(DetectionResult).count(),  # fcg-rewrite
                "user_detection_counts": [  # fcg-rewrite
                    {
                        "tenant_id": str(row.tenant_id),  # fcg-rewrite
                        "email": row.email,  # fcg-rewrite
                        "detection_count": row.detection_count,  # fcg-rewrite
                    }
                    for row in rows  # fcg-rewrite
                ],
            },
        }
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Get admin stats", exc)  # fcg-rewrite


@router.get("/admin/users")  # fcg-rewrite
async def get_all_users(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    sort_by: str = "created_at",  # fcg-rewrite
    sort_order: str = "desc",  # fcg-rewrite
    skip: int = 0,  # fcg-rewrite
    limit: int = 20,  # fcg-rewrite
    search: Optional[str] = None,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        admin = _require_admin(request, db)  # fcg-rewrite
        users, total = admin_service.get_all_users(  # fcg-rewrite
            db,
            admin,
            sort_by=sort_by if sort_by in {"created_at", "detection_count", "last_activity"} else "created_at",  # fcg-rewrite
            sort_order=sort_order if sort_order in {"asc", "desc"} else "desc",  # fcg-rewrite
            skip=max(skip, 0),  # fcg-rewrite
            limit=limit if 1 <= limit <= 100 else 20,  # fcg-rewrite
            search=search,  # fcg-rewrite
        )
        return {"status": "success", "users": users, "total": total}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except PermissionError as exc:  # fcg-rewrite
        raise HTTPException(status_code=403, detail=str(exc)) from exc  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _server_error("Get all users", exc)  # fcg-rewrite


@router.post("/admin/switch-user/{target_tenant_id}")  # fcg-rewrite
async def assume_user_identity(  # fcg-rewrite
    target_tenant_id: str, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        admin = _require_admin(request, db)  # fcg-rewrite
        token = admin_service.assume_user_identity(db, admin, target_tenant_id)  # fcg-rewrite
        target = _find_tenant(db, target_tenant_id)  # fcg-rewrite
        return {  # fcg-rewrite
            "status": "success",  # fcg-rewrite
            "message": f"Switched to tenant {target.email}",  # fcg-rewrite
            "switch_session_token": token,  # fcg-rewrite
            "target_user": {"id": str(target.id), "email": target.email, "api_key": target.api_key},  # fcg-rewrite
        }
    except HTTPException:  # fcg-rewrite
        raise
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(status_code=404, detail=str(exc)) from exc  # fcg-rewrite
    except PermissionError as exc:  # fcg-rewrite
        raise HTTPException(status_code=403, detail=str(exc)) from exc  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _server_error("Switch user", exc)  # fcg-rewrite


@router.post("/admin/exit-switch")  # fcg-rewrite
async def release_user_identity(  # fcg-rewrite
    x_switch_session: Optional[str] = Header(None), db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    if not x_switch_session:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="No switch session found")  # fcg-rewrite
    try:
        if not admin_service.release_user_identity(db, x_switch_session):  # fcg-rewrite
            raise HTTPException(status_code=404, detail="Switch session not found or already expired")  # fcg-rewrite
        return {"status": "success", "message": "Exited user switch view"}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Exit user switch", exc)  # fcg-rewrite


@router.get("/admin/current-switch")  # fcg-rewrite
async def get_current_switch_info(  # fcg-rewrite
    x_switch_session: Optional[str] = Header(None), db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    if not x_switch_session:  # fcg-rewrite
        return {"is_switched": False, "admin_user": None, "target_user": None}  # fcg-rewrite
    try:
        target = admin_service.resolve_assumed_user(db, x_switch_session)  # fcg-rewrite
        if not target:  # fcg-rewrite
            return {"is_switched": False, "admin_user": None, "target_user": None}  # fcg-rewrite
        admin = admin_service.resolve_admin_from_switch(db, x_switch_session)  # fcg-rewrite
        return {  # fcg-rewrite
            "is_switched": True,  # fcg-rewrite
            "admin_user": {"id": str(admin.id), "email": admin.email} if admin else None,  # fcg-rewrite
            "target_user": {"id": str(target.id), "email": target.email, "api_key": target.api_key},  # fcg-rewrite
        }
    except Exception as exc:  # fcg-rewrite
        _server_error("Get current switch info", exc)  # fcg-rewrite


class SetRateLimitRequest(BaseModel):  # fcg-rewrite
    tenant_id: str  # fcg-rewrite
    requests_per_second: int  # fcg-rewrite


class RateLimitResponse(BaseModel):  # fcg-rewrite
    tenant_id: str  # fcg-rewrite
    email: str  # fcg-rewrite
    requests_per_second: int  # fcg-rewrite
    is_active: bool  # fcg-rewrite


@router.get("/admin/rate-limits")  # fcg-rewrite
async def get_all_rate_limits(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    skip: int = 0,  # fcg-rewrite
    limit: int = 100,  # fcg-rewrite
    search: Optional[str] = None,  # fcg-rewrite
    sort_by: str = "requests_per_second",  # fcg-rewrite
    sort_order: str = "desc",  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        _require_admin(request, db)  # fcg-rewrite
        rows, total = RateLimitService(db).list_user_rate_limits(skip, limit, search, sort_by, sort_order)  # fcg-rewrite
        data = [  # fcg-rewrite
            RateLimitResponse(  # fcg-rewrite
                tenant_id=str(tenant.id),  # fcg-rewrite
                email=tenant.email,  # fcg-rewrite
                requests_per_second=rate_limit.requests_per_second if rate_limit else 1,  # fcg-rewrite
                is_active=rate_limit.is_active if rate_limit else False,  # fcg-rewrite
            )
            for tenant, rate_limit in rows  # fcg-rewrite
        ]
        return {"status": "success", "data": data, "total": total}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Get rate limits", exc)  # fcg-rewrite


@router.post("/admin/rate-limits")  # fcg-rewrite
async def set_user_rate_limit(  # fcg-rewrite
    request_data: SetRateLimitRequest, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        _require_admin(request, db)  # fcg-rewrite
        if request_data.requests_per_second < 0:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="requests_per_second must be >= 0")  # fcg-rewrite
        rate_limit = RateLimitService(db).set_user_rate_limit(  # fcg-rewrite
            request_data.tenant_id, request_data.requests_per_second  # fcg-rewrite
        )
        return {  # fcg-rewrite
            "status": "success",  # fcg-rewrite
            "message": f"Rate limit set for user {request_data.tenant_id}: {request_data.requests_per_second} rps",  # fcg-rewrite
            "data": {  # fcg-rewrite
                "tenant_id": str(rate_limit.tenant_id),  # fcg-rewrite
                "requests_per_second": rate_limit.requests_per_second,  # fcg-rewrite
                "is_active": rate_limit.is_active,  # fcg-rewrite
            },
        }
    except HTTPException:  # fcg-rewrite
        raise
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(status_code=404, detail=str(exc)) from exc  # fcg-rewrite
    except Exception as exc:  # fcg-rewrite
        _server_error("Set rate limit", exc)  # fcg-rewrite


@router.delete("/admin/rate-limits/{tenant_id}")  # fcg-rewrite
async def remove_user_rate_limit(  # fcg-rewrite
    tenant_id: str, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        _require_admin(request, db)  # fcg-rewrite
        RateLimitService(db).disable_user_rate_limit(tenant_id)  # fcg-rewrite
        return {"status": "success", "message": f"Rate limit removed for user {tenant_id}"}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Remove rate limit", exc)  # fcg-rewrite


class CreateUserRequest(BaseModel):  # fcg-rewrite
    email: EmailStr  # fcg-rewrite
    password: str  # fcg-rewrite
    is_active: bool = True  # fcg-rewrite
    is_verified: bool = False  # fcg-rewrite
    is_super_admin: bool = False  # fcg-rewrite


class UpdateUserRequest(BaseModel):  # fcg-rewrite
    email: Optional[EmailStr] = None  # fcg-rewrite
    is_active: Optional[bool] = None  # fcg-rewrite
    is_verified: Optional[bool] = None  # fcg-rewrite
    is_super_admin: Optional[bool] = None  # fcg-rewrite


@router.post("/admin/create-user")  # fcg-rewrite
async def create_user(  # fcg-rewrite
    request_data: CreateUserRequest, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        _require_admin(request, db)  # fcg-rewrite
        if db.query(Tenant).filter(Tenant.email == request_data.email).first():  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Email already exists")  # fcg-rewrite
        tenant = Tenant(  # fcg-rewrite
            email=request_data.email,  # fcg-rewrite
            password_hash=get_password_hash(request_data.password),  # fcg-rewrite
            is_active=request_data.is_active,  # fcg-rewrite
            is_verified=request_data.is_verified,  # fcg-rewrite
            is_super_admin=False,  # fcg-rewrite
            api_key=generate_api_key(),  # fcg-rewrite
        )
        db.add(tenant)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(tenant)  # fcg-rewrite
        return {  # fcg-rewrite
            "status": "success",  # fcg-rewrite
            "message": f"Tenant {tenant.email} created successfully",  # fcg-rewrite
            "data": {"tenant_id": str(tenant.id), "email": tenant.email},  # fcg-rewrite
        }
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Create user", exc, db)  # fcg-rewrite


@router.put("/admin/users/{tenant_id}")  # fcg-rewrite
async def update_user(  # fcg-rewrite
    tenant_id: str,  # fcg-rewrite
    request_data: UpdateUserRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    try:
        _require_admin(request, db)  # fcg-rewrite
        tenant = _find_tenant(db, tenant_id)  # fcg-rewrite
        changes = request_data.model_dump(exclude_unset=True)  # fcg-rewrite
        changes.pop("is_super_admin", None)  # fcg-rewrite
        for field, value in changes.items():  # fcg-rewrite
            setattr(tenant, field, value)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        return {"status": "success", "message": f"Tenant {tenant.email} updated successfully"}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Update user", exc, db)  # fcg-rewrite


_TENANT_SCOPED_MODELS = (  # fcg-rewrite
    TenantRateLimitCounter,  # fcg-rewrite
    TenantRateLimit,  # fcg-rewrite
    DetectionResult,  # fcg-rewrite
    TestModelConfig,  # fcg-rewrite
    Blacklist,  # fcg-rewrite
    Whitelist,  # fcg-rewrite
    ResponseTemplate,  # fcg-rewrite
    RiskTypeConfig,  # fcg-rewrite
    ProxyModelConfig,  # fcg-rewrite
    ProxyRequestLog,  # fcg-rewrite
    KnowledgeBase,  # fcg-rewrite
    OnlineTestModelSelection,  # fcg-rewrite
    DataSecurityEntityType,  # fcg-rewrite
    TenantSubscription,  # fcg-rewrite
)


@router.delete("/admin/users/{tenant_id}")  # fcg-rewrite
async def delete_user(tenant_id: str, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    try:
        admin = _require_admin(request, db)  # fcg-rewrite
        tenant_uuid = _uuid(tenant_id)  # fcg-rewrite
        tenant = _find_tenant(db, tenant_id)  # fcg-rewrite
        if tenant.id == admin.id:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Cannot delete your own account")  # fcg-rewrite
        for model in _TENANT_SCOPED_MODELS:  # fcg-rewrite
            db.query(model).filter(model.tenant_id == tenant_uuid).delete()  # fcg-rewrite
        db.query(TenantSwitch).filter(  # fcg-rewrite
            (TenantSwitch.admin_tenant_id == tenant_uuid)  # fcg-rewrite
            | (TenantSwitch.target_tenant_id == tenant_uuid)  # fcg-rewrite
        ).delete()  # fcg-rewrite
        db.delete(tenant)  # fcg-rewrite
        db.commit()  # fcg-rewrite
        return {"status": "success", "message": f"Tenant {tenant.email} deleted successfully"}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Delete user", exc, db)  # fcg-rewrite


@router.post("/admin/users/{tenant_id}/reset-api-key")  # fcg-rewrite
async def reset_user_api_key(  # fcg-rewrite
    tenant_id: str, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        _require_admin(request, db)  # fcg-rewrite
        tenant = _find_tenant(db, tenant_id)  # fcg-rewrite
        tenant.api_key = generate_api_key()  # fcg-rewrite
        db.commit()  # fcg-rewrite
        return {  # fcg-rewrite
            "status": "success",  # fcg-rewrite
            "message": f"API key reset for tenant {tenant.email}",  # fcg-rewrite
            "data": {"new_api_key": tenant.api_key},  # fcg-rewrite
        }
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Reset API key", exc, db)  # fcg-rewrite


def _tenant_summary(tenant: Tenant) -> dict:  # fcg-rewrite
    return {  # fcg-rewrite
        "id": str(tenant.id),  # fcg-rewrite
        "email": tenant.email,  # fcg-rewrite
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,  # fcg-rewrite
        "is_active": tenant.is_active,  # fcg-rewrite
        "is_verified": tenant.is_verified,  # fcg-rewrite
    }


def _trend(db: Session, model, start_date, days: int) -> list[dict]:  # fcg-rewrite
    rows = db.query(  # fcg-rewrite
        func.date(model.created_at).label("date"), func.count(model.id).label("count")  # fcg-rewrite
    ).filter(func.date(model.created_at) >= start_date).group_by(  # fcg-rewrite
        func.date(model.created_at)  # fcg-rewrite
    ).order_by(func.date(model.created_at)).all()  # fcg-rewrite
    counts = {str(row.date): row.count for row in rows}  # fcg-rewrite
    return [  # fcg-rewrite
        {"date": str(start_date + timedelta(days=offset)), "count": counts.get(str(start_date + timedelta(days=offset)), 0)}  # fcg-rewrite
        for offset in range(days)  # fcg-rewrite
    ]


@router.get("/admin/tenant-analytics")  # fcg-rewrite
async def get_tenant_analytics(  # fcg-rewrite
    request: Request, days: int = 30, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    try:
        _require_admin(request, db)  # fcg-rewrite
        latest = db.query(Tenant).order_by(desc(Tenant.created_at)).limit(10).all()  # fcg-rewrite
        recent_rows = db.query(  # fcg-rewrite
            Tenant.id,  # fcg-rewrite
            Tenant.email,  # fcg-rewrite
            Tenant.is_active,  # fcg-rewrite
            Tenant.is_verified,  # fcg-rewrite
            func.max(DetectionResult.created_at).label("last_activity"),  # fcg-rewrite
        ).join(DetectionResult, Tenant.id == DetectionResult.tenant_id).filter(  # fcg-rewrite
            DetectionResult.created_at >= datetime.now() - timedelta(days=7)  # fcg-rewrite
        ).group_by(Tenant.id, Tenant.email, Tenant.is_active, Tenant.is_verified).order_by(  # fcg-rewrite
            desc("last_activity")  # fcg-rewrite
        ).limit(10).all()  # fcg-rewrite
        recent = [  # fcg-rewrite
            {
                "id": str(row.id),  # fcg-rewrite
                "email": row.email,  # fcg-rewrite
                "last_activity": row.last_activity.isoformat() if row.last_activity else None,  # fcg-rewrite
                "is_active": row.is_active,  # fcg-rewrite
                "is_verified": row.is_verified,  # fcg-rewrite
            }
            for row in recent_rows  # fcg-rewrite
        ]
        start = datetime.now().date() - timedelta(days=days - 1)  # fcg-rewrite
        return {  # fcg-rewrite
            "status": "success",  # fcg-rewrite
            "data": {  # fcg-rewrite
                "latest_created_tenants": [_tenant_summary(tenant) for tenant in latest],  # fcg-rewrite
                "recently_active_tenants": recent,  # fcg-rewrite
                "creation_trend": _trend(db, Tenant, start, days),  # fcg-rewrite
                "usage_trend": _trend(db, DetectionResult, start, days),  # fcg-rewrite
            },
        }
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as exc:  # fcg-rewrite
        _server_error("Get tenant analytics", exc)  # fcg-rewrite
