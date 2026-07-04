"""Scanner package catalog, marketplace, and administrator operations."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_admin_db
from models.requests import PackageUpdateRequest, PackageUploadRequest
from models.responses import ApiResponse, MarketplacePackageResponse, PackageDetailResponse, PackageResponse, PackageStatisticsResponse
from services.scanner_package_service import ScannerPackageService

router = APIRouter(prefix="/api/v1/scanner-packages", tags=["Scanner Packages"])


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


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid package ID format") from exc


def _marketplace_enabled():
    if settings.is_enterprise_mode:
        raise HTTPException(status_code=404, detail="Marketplace is not available in enterprise deployment mode")


def _package_response(package) -> PackageResponse:
    return PackageResponse(
        id=str(package.id),
        package_code=package.package_code,
        package_name=package.package_name,
        author=package.author,
        description=package.description,
        version=package.version,
        license=package.license,
        package_type=package.package_type,
        scanner_count=package.scanner_count,
        price=package.price,
        price_display=package.price_display,
        bundle=package.bundle,
        created_at=package.created_at.isoformat() if package.created_at else None,
        updated_at=package.updated_at.isoformat() if package.updated_at else None,
        archived=getattr(package, "archived", False),
        archived_at=package.archived_at.isoformat() if getattr(package, "archived_at", None) else None,
        archive_reason=getattr(package, "archive_reason", None),
    )


def _package_type(package_type: Optional[str]) -> Optional[str]:
    return "basic" if package_type == "builtin" else package_type


@router.get("/", response_model=List[PackageResponse])
async def get_all_packages(
    request: Request, package_type: Optional[str] = None, db: Session = Depends(get_admin_db)
):
    user = get_current_user(request)
    visible_type = "basic" if settings.is_enterprise_mode else _package_type(package_type)
    packages = ScannerPackageService(db).get_all_packages(
        tenant_id=UUID(user["tenant_id"]), package_type=visible_type, include_scanners=False
    )
    return [_package_response(package) for package in packages]


@router.get("/{package_id}", response_model=PackageDetailResponse)
async def get_package_detail(package_id: str, request: Request, db: Session = Depends(get_admin_db)):
    user = get_current_user(request)
    detail = ScannerPackageService(db).get_package_detail(_uuid(package_id), UUID(user["tenant_id"]))
    if not detail:
        raise HTTPException(status_code=404, detail="Package not found or access denied")
    return PackageDetailResponse(**detail)


@router.get("/marketplace/list", response_model=List[MarketplacePackageResponse])
async def get_marketplace_packages(request: Request, db: Session = Depends(get_admin_db)):
    _marketplace_enabled()
    user = get_current_user(request)
    return [
        MarketplacePackageResponse(**package)
        for package in ScannerPackageService(db).get_purchasable_packages(UUID(user["tenant_id"]))
    ]


@router.get("/marketplace/{package_id}", response_model=PackageDetailResponse)
async def get_marketplace_package_detail(
    package_id: str, request: Request, db: Session = Depends(get_admin_db)
):
    _marketplace_enabled()
    user = get_current_user(request)
    detail = ScannerPackageService(db).get_marketplace_package_detail(_uuid(package_id), UUID(user["tenant_id"]))
    if not detail:
        raise HTTPException(status_code=404, detail="Package not found")
    return PackageDetailResponse(**detail)


@router.get("/admin/packages", response_model=List[PackageResponse])
async def get_all_packages_admin(
    request: Request,
    package_type: Optional[str] = None,
    include_archived: Optional[bool] = False,
    db: Session = Depends(get_admin_db),
    current_user: dict = Depends(require_super_admin),
):
    packages = ScannerPackageService(db).get_all_packages_admin(_package_type(package_type), include_archived)
    return [_package_response(package) for package in packages]


def _price_display(price: Optional[float], language: str) -> str:
    value = int(price) if isinstance(price, float) and price.is_integer() else price
    if value is None:
        return "免费" if language == "zh" else "Free"
    return f"￥{value}元" if language == "zh" else f"${value}"


@router.post("/admin/upload", response_model=PackageResponse)
async def upload_premium_package(
    upload_request: PackageUploadRequest,
    request: Request,
    db: Session = Depends(get_admin_db),
    current_user: dict = Depends(require_super_admin),
):
    data = dict(upload_request.package_data)
    data.update(price=upload_request.price, price_display=_price_display(upload_request.price, upload_request.language))
    if upload_request.bundle:
        data["bundle"] = upload_request.bundle
    try:
        package = ScannerPackageService(db).create_purchasable_package(data, UUID(current_user["tenant_id"]))
        return _package_response(package)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to upload package: {exc}") from exc


@router.put("/admin/{package_id}", response_model=PackageResponse)
async def update_package(
    package_id: str,
    updates: PackageUpdateRequest,
    request: Request,
    db: Session = Depends(get_admin_db),
    current_user: dict = Depends(require_super_admin),
):
    package = ScannerPackageService(db).update_package(_uuid(package_id), updates.model_dump(exclude_unset=True))
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    return _package_response(package)


def _archive(service: ScannerPackageService, package_id: str, user: dict, reason: Optional[str]):
    if not service.archive_package(_uuid(package_id), UUID(user["tenant_id"]), reason):
        raise HTTPException(status_code=404, detail="Package not found")


@router.post("/admin/{package_id}/archive", response_model=ApiResponse)
async def archive_package(
    package_id: str,
    request: Request,
    archive_data: Optional[dict] = None,
    db: Session = Depends(get_admin_db),
    current_user: dict = Depends(require_super_admin),
):
    _archive(ScannerPackageService(db), package_id, current_user, (archive_data or {}).get("reason"))
    return ApiResponse(success=True, message="Package archived successfully")


@router.post("/admin/{package_id}/unarchive", response_model=ApiResponse)
async def unarchive_package(
    package_id: str,
    request: Request,
    db: Session = Depends(get_admin_db),
    current_user: dict = Depends(require_super_admin),
):
    if not ScannerPackageService(db).unarchive_package(_uuid(package_id), UUID(current_user["tenant_id"])):
        raise HTTPException(status_code=404, detail="Package not found or not archived")
    return ApiResponse(success=True, message="Package unarchived successfully")


@router.delete("/admin/{package_id}", response_model=ApiResponse)
async def delete_package(
    package_id: str,
    request: Request,
    db: Session = Depends(get_admin_db),
    current_user: dict = Depends(require_super_admin),
):
    _archive(ScannerPackageService(db), package_id, current_user, "Legacy delete operation")
    return ApiResponse(success=True, message="Package archived (legacy delete)")


@router.get("/admin/{package_id}/statistics", response_model=PackageStatisticsResponse)
async def get_package_statistics(
    package_id: str,
    request: Request,
    db: Session = Depends(get_admin_db),
    current_user: dict = Depends(require_super_admin),
):
    stats = ScannerPackageService(db).get_package_statistics(_uuid(package_id))
    if not stats:
        raise HTTPException(status_code=404, detail="Package not found")
    return PackageStatisticsResponse(**stats)
