"""Per-application scanner configuration endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from database.connection import get_admin_db
from models.requests import ScannerConfigBulkUpdateRequest, ScannerConfigUpdateRequest
from models.responses import ApiResponse, ScannerConfigResponse
from services.scanner_config_service import ScannerConfigService
from utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/api/v1/scanner-configs", tags=["Scanner Configs"])


def get_current_user(request: Request) -> dict:
    auth_context = getattr(request.state, "auth_context", None)
    if not isinstance(auth_context, dict):
        raise HTTPException(status_code=401, detail="Invalid auth context" if auth_context else "Not authenticated")
    return auth_context.get("data", auth_context)


def require_super_admin(request: Request) -> dict:
    user = get_current_user(request)
    if not user.get("is_super_admin"):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


def _uuid(value: str, detail: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def get_application_id(request: Request, x_application_id: Optional[str] = Header(None)) -> UUID:
    if x_application_id:
        return _uuid(x_application_id, "Invalid X-Application-ID format")
    application_id = get_current_user(request).get("application_id")
    if application_id:
        return _uuid(application_id, "Invalid application ID format")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No application context. Please provide X-Application-ID header.",
    )


def _context(request: Request, db: Session):
    user = get_current_user(request)
    return user, ScannerConfigService(db)


def _response(message: str, **data) -> ApiResponse:
    return ApiResponse(success=True, message=message, data=data or None)


@router.get("", response_model=List[ScannerConfigResponse])
async def get_application_scanners(
    request: Request,
    include_disabled: bool = True,
    application_id: UUID = Depends(get_application_id),
    db: Session = Depends(get_admin_db),
):
    user, service = _context(request, db)
    scanners = service.get_application_scanners(application_id, UUID(user["tenant_id"]), include_disabled)
    result = [ScannerConfigResponse(**scanner) for scanner in scanners]
    logger.info("User %s retrieved %s scanner configs for app=%s", user["email"], len(result), application_id)
    return result


@router.get("/enabled", response_model=List[ScannerConfigResponse])
async def get_enabled_scanners(
    request: Request,
    scan_type: Optional[str] = None,
    application_id: UUID = Depends(get_application_id),
    db: Session = Depends(get_admin_db),
):
    if scan_type and scan_type not in {"prompt", "response"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scan_type must be 'prompt' or 'response'")
    user, service = _context(request, db)
    scanners = service.get_enabled_scanners(application_id, UUID(user["tenant_id"]), scan_type)
    result = [ScannerConfigResponse(**scanner) for scanner in scanners]
    logger.info("User %s retrieved %s enabled scanners (type=%s) for app=%s", user["email"], len(result), scan_type, application_id)
    return result


@router.put("/{scanner_id}", response_model=ApiResponse)
async def update_scanner_config(
    request: Request,
    scanner_id: str,
    updates: ScannerConfigUpdateRequest,
    application_id: UUID = Depends(get_application_id),
    db: Session = Depends(get_admin_db),
):
    user, service = _context(request, db)
    payload = updates.model_dump(exclude_unset=True)
    try:
        config = service.update_scanner_config(application_id, _uuid(scanner_id, "Invalid scanner ID format"), payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    logger.info("User %s updated scanner config app=%s, scanner=%s, updates=%s", user["email"], application_id, scanner_id, list(payload))
    return _response("Scanner configuration updated successfully", config_id=str(config.id))


@router.post("/bulk-update", response_model=ApiResponse)
async def bulk_update_scanner_configs(
    request: Request,
    bulk_updates: ScannerConfigBulkUpdateRequest,
    application_id: UUID = Depends(get_application_id),
    db: Session = Depends(get_admin_db),
):
    user, service = _context(request, db)
    payload = [item.model_dump(exclude_unset=True) for item in bulk_updates.updates]
    try:
        configs = service.bulk_update_scanner_configs(application_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    logger.info("User %s bulk updated %s scanner configs for app=%s", user["email"], len(configs), application_id)
    return _response(f"Successfully updated {len(configs)} scanner configurations", updated_count=len(configs))


@router.post("/{scanner_id}/reset", response_model=ApiResponse)
async def reset_scanner_config(
    request: Request,
    scanner_id: str,
    application_id: UUID = Depends(get_application_id),
    db: Session = Depends(get_admin_db),
):
    user, service = _context(request, db)
    if not service.reset_scanner_config(application_id, _uuid(scanner_id, "Invalid scanner ID format")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scanner configuration not found")
    logger.info("User %s reset scanner config app=%s, scanner=%s", user["email"], application_id, scanner_id)
    return _response("Scanner configuration reset to defaults")


@router.post("/reset-all", response_model=ApiResponse)
async def reset_all_configs(
    request: Request,
    application_id: UUID = Depends(get_application_id),
    db: Session = Depends(get_admin_db),
):
    user, service = _context(request, db)
    count = service.reset_all_configs(application_id)
    logger.warning("User %s reset all %s scanner configs for app=%s", user["email"], count, application_id)
    return _response(f"Successfully reset {count} scanner configurations to defaults", reset_count=count)


@router.post("/initialize", response_model=ApiResponse)
async def initialize_default_configs(
    request: Request,
    application_id: UUID = Depends(get_application_id),
    db: Session = Depends(get_admin_db),
):
    user, service = _context(request, db)
    count = service.initialize_default_configs(application_id, UUID(user["tenant_id"]))
    logger.info("User %s initialized %s default scanner configs for app=%s", user["email"], count, application_id)
    return _response(f"Initialized {count} scanner configurations", initialized_count=count)
