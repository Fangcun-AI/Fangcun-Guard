"""Scanner-package purchase request and approval routes."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database.connection import get_admin_db
from models.requests import PurchaseApprovalRequest, PurchaseRequestCreate
from models.responses import ApiResponse, PurchasePendingResponse, PurchaseResponse
from services.purchase_service import PurchaseService
from utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/api/v1/purchases", tags=["Package Purchases"])


def get_current_user(request: Request) -> dict:
    context = getattr(request.state, "auth_context", None)
    if isinstance(context, dict):
        return context.get("data", context)
    raise HTTPException(status_code=401, detail="Not authenticated" if not context else "Invalid auth context")


def require_super_admin(request: Request) -> dict:
    user = get_current_user(request)
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


def _uuid(value: str, label: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label} ID format") from exc


def _response(purchase) -> PurchaseResponse:
    package = purchase.package
    return PurchaseResponse(
        id=str(purchase.id),
        package_id=str(purchase.package_id),
        package_name=package.package_name if package else None,
        package_code=package.package_code if package else None,
        status=purchase.status,
        request_email=purchase.request_email,
        request_message=purchase.request_message,
        rejection_reason=purchase.rejection_reason,
        approved_at=purchase.approved_at.isoformat() if purchase.approved_at else None,
        created_at=purchase.created_at.isoformat() if purchase.created_at else None,
    )


def _service_error(exc: ValueError):
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/direct", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def direct_purchase_free_package(
    request: Request, request_data: PurchaseRequestCreate, db: Session = Depends(get_admin_db)
):
    user = get_current_user(request)
    try:
        purchase = PurchaseService(db).direct_purchase_free_package(
            tenant_id=UUID(user["tenant_id"]),
            package_id=_uuid(request_data.package_id, "package"),
            email=request_data.email,
        )
        return _response(purchase)
    except ValueError as exc:
        _service_error(exc)


@router.post("/request", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def request_purchase(
    request: Request, request_data: PurchaseRequestCreate, db: Session = Depends(get_admin_db)
):
    user = get_current_user(request)
    try:
        purchase = PurchaseService(db).request_purchase(
            tenant_id=UUID(user["tenant_id"]),
            package_id=_uuid(request_data.package_id, "package"),
            email=request_data.email,
            message=request_data.message,
        )
        return _response(purchase)
    except ValueError as exc:
        _service_error(exc)


@router.get("/my-purchases", response_model=List[PurchaseResponse])
async def get_my_purchases(
    request: Request, status_filter: Optional[str] = None, db: Session = Depends(get_admin_db)
):
    if status_filter and status_filter not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be 'pending', 'approved', or 'rejected'")
    user = get_current_user(request)
    purchases = PurchaseService(db).get_user_purchases(UUID(user["tenant_id"]), status_filter)
    return [PurchaseResponse(**purchase) for purchase in purchases]


@router.delete("/{purchase_id}", response_model=ApiResponse)
async def cancel_purchase_request(
    request: Request, purchase_id: str, db: Session = Depends(get_admin_db)
):
    user = get_current_user(request)
    success = PurchaseService(db).cancel_purchase_request(
        _uuid(purchase_id, "purchase"), UUID(user["tenant_id"])
    )
    if not success:
        raise HTTPException(status_code=404, detail="Purchase request not found or cannot be cancelled")
    return ApiResponse(success=True, message="Purchase request cancelled successfully")


@router.get("/admin/pending", response_model=List[PurchasePendingResponse])
async def get_pending_purchases(request: Request, db: Session = Depends(get_admin_db)):
    require_super_admin(request)
    return [PurchasePendingResponse(**purchase) for purchase in PurchaseService(db).get_pending_purchases()]


@router.post("/admin/{purchase_id}/approve", response_model=PurchaseResponse)
async def approve_purchase(request: Request, purchase_id: str, db: Session = Depends(get_admin_db)):
    user = require_super_admin(request)
    try:
        purchase = PurchaseService(db).approve_purchase(
            _uuid(purchase_id, "purchase"), UUID(user["tenant_id"])
        )
    except ValueError as exc:
        _service_error(exc)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    return _response(purchase)


@router.post("/admin/{purchase_id}/reject", response_model=PurchaseResponse)
async def reject_purchase(
    request: Request,
    purchase_id: str,
    rejection_data: PurchaseApprovalRequest,
    db: Session = Depends(get_admin_db),
):
    user = require_super_admin(request)
    if not rejection_data.rejection_reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    try:
        purchase = PurchaseService(db).reject_purchase(
            _uuid(purchase_id, "purchase"),
            rejection_data.rejection_reason,
            UUID(user["tenant_id"]),
        )
    except ValueError as exc:
        _service_error(exc)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    return _response(purchase)


@router.get("/admin/statistics", response_model=ApiResponse)
async def get_purchase_statistics(
    request: Request, package_id: Optional[str] = None, db: Session = Depends(get_admin_db)
):
    require_super_admin(request)
    stats = PurchaseService(db).get_purchase_statistics(
        package_id=_uuid(package_id, "package") if package_id else None
    )
    return ApiResponse(success=True, message="Purchase statistics retrieved successfully", data=stats)
