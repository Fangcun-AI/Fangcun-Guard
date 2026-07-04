"""
Custom Scanner API Router
Handles user-defined custom scanners (S100+)
"""

from typing import List, Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.connection import get_admin_db  # fcg-rewrite
from database.models import TenantSubscription  # fcg-rewrite
from services.custom_scanner_service import CustomScannerRegistryService  # fcg-rewrite
from models.requests import CustomScannerCreateRequest, CustomScannerUpdateRequest  # fcg-rewrite
from models.responses import CustomScannerResponse, ApiResponse  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite

router = APIRouter(prefix="/api/v1/custom-scanners", tags=["Custom Scanners"])  # fcg-rewrite


def get_current_user(request: Request) -> dict:  # fcg-rewrite
    """Get current user from request context"""
    auth_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
    if not auth_context:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite

    # Handle both auth_context formats: direct dict and {data: dict}
    if isinstance(auth_context, dict) and 'data' in auth_context:  # fcg-rewrite
        return auth_context['data']  # fcg-rewrite
    elif isinstance(auth_context, dict):  # fcg-rewrite
        return auth_context  # fcg-rewrite
    else:
        raise HTTPException(status_code=401, detail="Invalid auth context")  # fcg-rewrite


def require_super_admin(request: Request) -> dict:  # fcg-rewrite
    """Require super admin access"""
    user = get_current_user(request)  # fcg-rewrite
    if not user.get('is_super_admin'):  # fcg-rewrite
        raise HTTPException(status_code=403, detail="Super admin access required")  # fcg-rewrite
    return user  # fcg-rewrite


def require_subscription(request: Request, db: Session) -> dict:  # fcg-rewrite
    """
    Require subscribed user access for custom scanner features.
    Custom scanners are a premium feature only available to subscribed users.
    Super admins automatically have subscription access.
    """
    user = get_current_user(request)  # fcg-rewrite
    tenant_id = UUID(user['tenant_id'])  # fcg-rewrite
    
    # Check if user is super admin - they automatically have subscription access
    if user.get('is_super_admin'):  # fcg-rewrite
        return user  # fcg-rewrite
    
    # Check subscription status
    subscription = db.query(TenantSubscription).filter(  # fcg-rewrite
        TenantSubscription.tenant_id == tenant_id  # fcg-rewrite
    ).first()  # fcg-rewrite
    
    # If no subscription found or not subscribed, deny access
    if not subscription or subscription.subscription_type != 'subscribed':  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_403_FORBIDDEN,  # fcg-rewrite
            detail="Custom scanners are a premium feature. Please upgrade to a subscribed plan to access this feature."  # fcg-rewrite
        )
    
    return user  # fcg-rewrite



def get_application_id(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    x_application_id: Optional[str] = Header(None)  # fcg-rewrite
) -> UUID:  # fcg-rewrite
    """
    Extract application ID from header or use default.
    """
    if x_application_id:  # fcg-rewrite
        try:
            return UUID(x_application_id)  # fcg-rewrite
        except ValueError:  # fcg-rewrite
            raise HTTPException(  # fcg-rewrite
                status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
                detail="Invalid X-Application-ID format"  # fcg-rewrite
            )

    # Use default application ID from user context
    current_user = get_current_user(request)  # fcg-rewrite
    if current_user and 'application_id' in current_user and current_user['application_id']:  # fcg-rewrite
        return UUID(current_user['application_id'])  # fcg-rewrite

    raise HTTPException(  # fcg-rewrite
        status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
        detail="No application context. Please provide X-Application-ID header."  # fcg-rewrite
    )


# =====================================================
# Custom Scanner CRUD Endpoints
# =====================================================

@router.get("", response_model=List[CustomScannerResponse])  # fcg-rewrite
async def get_custom_scanners(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    application_id: UUID = Depends(get_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """
    Get all custom scanners for application.

    Returns only active custom scanners (S100+) created by this application.
    
    **Premium Feature**: Requires subscribed plan.
    """
    current_user = require_subscription(request, db)  # fcg-rewrite
    service = CustomScannerRegistryService(db)  # fcg-rewrite

    scanners = service.get_custom_scanners(application_id)  # fcg-rewrite

    result = [CustomScannerResponse(**scanner) for scanner in scanners]  # fcg-rewrite

    logger.info(  # fcg-rewrite
        f"User {current_user['email']} retrieved {len(result)} custom scanners "  # fcg-rewrite
        f"for app={application_id}"  # fcg-rewrite
    )

    return result  # fcg-rewrite


@router.get("/{scanner_id}", response_model=CustomScannerResponse)  # fcg-rewrite
async def get_custom_scanner(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    scanner_id: str,  # fcg-rewrite
    application_id: UUID = Depends(get_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """
    Get custom scanner details by ID.
    
    **Premium Feature**: Requires subscribed plan.
    """
    current_user = require_subscription(request, db)  # fcg-rewrite
    service = CustomScannerRegistryService(db)  # fcg-rewrite

    try:
        scanner_uuid = UUID(scanner_id)  # fcg-rewrite
    except ValueError:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail="Invalid scanner ID format"  # fcg-rewrite
        )

    scanner = service.get_custom_scanner(  # fcg-rewrite
        scanner_id=scanner_uuid,  # fcg-rewrite
        application_id=application_id  # fcg-rewrite
    )

    if not scanner:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_404_NOT_FOUND,  # fcg-rewrite
            detail="Custom scanner not found"  # fcg-rewrite
        )

    logger.info(  # fcg-rewrite
        f"User {current_user['email']} retrieved custom scanner {scanner_id}"  # fcg-rewrite
    )

    return CustomScannerResponse(**scanner)  # fcg-rewrite


@router.post("", response_model=CustomScannerResponse, status_code=status.HTTP_201_CREATED)  # fcg-rewrite
async def create_custom_scanner(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    scanner_data: CustomScannerCreateRequest,  # fcg-rewrite
    application_id: UUID = Depends(get_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """
    Create a new custom scanner.

    Features:
    - Auto-assigned tag (S100, S101, S102, ...)
    - Validates scanner type (genai, regex, keyword)
    - Validates risk level (high_risk, medium_risk, low_risk)
    - No limits on number of custom scanners

    Scanner types:
    - genai: Calls Qwen3Guard-Gen-8B model
    - regex: Python regex pattern matching
    - keyword: Case-insensitive keyword matching
    
    **Premium Feature**: Requires subscribed plan.
    """
    current_user = require_subscription(request, db)  # fcg-rewrite
    service = CustomScannerRegistryService(db)  # fcg-rewrite
    tenant_id = UUID(current_user['tenant_id'])  # fcg-rewrite

    scanner_dict = scanner_data.model_dump()  # fcg-rewrite

    try:
        scanner = service.create_custom_scanner(  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            scanner_data=scanner_dict  # fcg-rewrite
        )
    except ValueError as e:  # fcg-rewrite
        # Handle validation errors
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail=str(e)  # fcg-rewrite
        )

    logger.info(  # fcg-rewrite
        f"User {current_user['email']} created custom scanner: "  # fcg-rewrite
        f"{scanner['tag']} ({scanner['name']}) type={scanner['scanner_type']} "  # fcg-rewrite
        f"for app={application_id}"  # fcg-rewrite
    )

    return CustomScannerResponse(**scanner)  # fcg-rewrite


@router.put("/{scanner_id}", response_model=CustomScannerResponse)  # fcg-rewrite
async def update_custom_scanner(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    scanner_id: str,  # fcg-rewrite
    updates: CustomScannerUpdateRequest,  # fcg-rewrite
    application_id: UUID = Depends(get_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """
    Update custom scanner.

    Note: Cannot update scanner_type or tag (would break detection logic).
    Can update: name, description, definition, risk_level, scan_prompt, scan_response, notes
    
    **Premium Feature**: Requires subscribed plan.
    """
    current_user = require_subscription(request, db)  # fcg-rewrite
    service = CustomScannerRegistryService(db)  # fcg-rewrite

    try:
        scanner_uuid = UUID(scanner_id)  # fcg-rewrite
    except ValueError:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail="Invalid scanner ID format"  # fcg-rewrite
        )

    update_dict = updates.model_dump(exclude_unset=True)  # fcg-rewrite

    scanner = service.update_custom_scanner(  # fcg-rewrite
        scanner_id=scanner_uuid,  # fcg-rewrite
        application_id=application_id,  # fcg-rewrite
        updates=update_dict  # fcg-rewrite
    )

    if not scanner:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_404_NOT_FOUND,  # fcg-rewrite
            detail="Custom scanner not found"  # fcg-rewrite
        )

    logger.info(  # fcg-rewrite
        f"User {current_user['email']} updated custom scanner {scanner_id}, "  # fcg-rewrite
        f"fields: {list(update_dict.keys())}"  # fcg-rewrite
    )

    return CustomScannerResponse(**scanner)  # fcg-rewrite


@router.delete("/{scanner_id}", response_model=ApiResponse)  # fcg-rewrite
async def delete_custom_scanner(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    scanner_id: str,  # fcg-rewrite
    application_id: UUID = Depends(get_application_id),  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """
    Delete custom scanner (soft delete).

    This will mark the scanner as inactive and cascade disable
    in all scanner configurations.
    
    **Premium Feature**: Requires subscribed plan.
    """
    current_user = require_subscription(request, db)  # fcg-rewrite
    service = CustomScannerRegistryService(db)  # fcg-rewrite

    try:
        scanner_uuid = UUID(scanner_id)  # fcg-rewrite
    except ValueError:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail="Invalid scanner ID format"  # fcg-rewrite
        )

    success = service.delete_custom_scanner(  # fcg-rewrite
        scanner_id=scanner_uuid,  # fcg-rewrite
        application_id=application_id  # fcg-rewrite
    )

    if not success:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_404_NOT_FOUND,  # fcg-rewrite
            detail="Custom scanner not found"  # fcg-rewrite
        )

    logger.warning(  # fcg-rewrite
        f"User {current_user['email']} deleted custom scanner {scanner_id} "  # fcg-rewrite
        f"from app={application_id}"  # fcg-rewrite
    )

    return ApiResponse(  # fcg-rewrite
        success=True,  # fcg-rewrite
        message="Custom scanner deleted successfully"  # fcg-rewrite
    )


# =====================================================
# Utility Endpoints
# =====================================================
