"""
Ban policy API routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request  # fcg-rewrite
from pydantic import BaseModel, Field  # fcg-rewrite
from typing import Optional, List  # fcg-rewrite
from services.ban_policy_service import BanPolicyManager  # fcg-rewrite
from services.application_request_context import resolve_admin_application_context  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
import logging  # fcg-rewrite

def get_current_application_id(request: Request, db: Session = Depends(get_admin_db)) -> str:  # fcg-rewrite
    """Get current application ID from shared request context."""
    context = resolve_admin_application_context(request, db)  # fcg-rewrite
    return str(context.application_id)  # fcg-rewrite

logger = logging.getLogger(__name__)  # fcg-rewrite

router = APIRouter(prefix="/api/v1/ban-policy", tags=["ban-policy"])  # fcg-rewrite


class BanPolicyUpdate(BaseModel):  # fcg-rewrite
    """Ban policy update model"""
    enabled: bool = Field(False, description="Whether to enable ban policy")  # fcg-rewrite
    risk_level: str = Field("high_risk", description="Minimum risk level to trigger ban", pattern="^(high_risk|medium_risk|low_risk)$")  # fcg-rewrite
    trigger_count: int = Field(3, ge=1, le=100, description="Trigger count threshold")  # fcg-rewrite
    time_window_minutes: int = Field(10, ge=1, le=1440, description="Time window (minutes)")  # fcg-rewrite
    ban_duration_minutes: int = Field(60, ge=1, le=10080, description="Ban duration (minutes)")  # fcg-rewrite


class UnbanUserRequest(BaseModel):  # fcg-rewrite
    """Unban user request model"""
    user_id: str = Field(..., description="User ID to unban")  # fcg-rewrite


@router.get("")  # fcg-rewrite
async def get_ban_policy(application_id: str = Depends(get_current_application_id)):  # fcg-rewrite
    """Get current application's ban policy configuration"""
    try:
        policy = await BanPolicyManager.get_ban_policy(application_id)  # fcg-rewrite

        if not policy:  # fcg-rewrite
            # If no policy, return default values
            return {  # fcg-rewrite
                "enabled": False,  # fcg-rewrite
                "risk_level": "high_risk",  # fcg-rewrite
                "trigger_count": 3,  # fcg-rewrite
                "time_window_minutes": 10,  # fcg-rewrite
                "ban_duration_minutes": 60  # fcg-rewrite
            }

        return policy  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to get ban policy: {str(e)}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to get ban policy: {str(e)}")  # fcg-rewrite


@router.put("")  # fcg-rewrite
async def update_ban_policy(  # fcg-rewrite
    policy_data: BanPolicyUpdate,  # fcg-rewrite
    application_id: str = Depends(get_current_application_id)  # fcg-rewrite
):
    """Update ban policy configuration"""
    try:
        policy = await BanPolicyManager.update_ban_policy(  # fcg-rewrite
            application_id,  # fcg-rewrite
            policy_data.dict()  # fcg-rewrite
        )

        return {  # fcg-rewrite
            "success": True,  # fcg-rewrite
            "message": "Ban policy updated",  # fcg-rewrite
            "policy": policy  # fcg-rewrite
        }

    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to update ban policy: {str(e)}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to update ban policy: {str(e)}")  # fcg-rewrite


@router.get("/templates")  # fcg-rewrite
async def get_ban_policy_templates():  # fcg-rewrite
    """Get ban policy preset templates"""
    return {  # fcg-rewrite
        "templates": [  # fcg-rewrite
            {
                "name": "Strict mode",  # fcg-rewrite
                "description": "High security requirements",  # fcg-rewrite
                "enabled": True,  # fcg-rewrite
                "risk_level": "high_risk",  # fcg-rewrite
                "trigger_count": 3,  # fcg-rewrite
                "time_window_minutes": 10,  # fcg-rewrite
                "ban_duration_minutes": 60  # fcg-rewrite
            },
            {
                "name": "Standard mode",  # fcg-rewrite
                "description": "Balance security and user experience",  # fcg-rewrite
                "enabled": True,  # fcg-rewrite
                "risk_level": "high_risk",  # fcg-rewrite
                "trigger_count": 5,  # fcg-rewrite
                "time_window_minutes": 30,  # fcg-rewrite
                "ban_duration_minutes": 30  # fcg-rewrite
            },
            {
                "name": "Relaxed mode",  # fcg-rewrite
                "description": "Test or low risk scenarios",  # fcg-rewrite
                "enabled": True,  # fcg-rewrite
                "risk_level": "high_risk",  # fcg-rewrite
                "trigger_count": 10,  # fcg-rewrite
                "time_window_minutes": 60,  # fcg-rewrite
                "ban_duration_minutes": 15  # fcg-rewrite
            },
            {
                "name": "Disabled",  # fcg-rewrite
                "description": "Disable ban policy",  # fcg-rewrite
                "enabled": False,  # fcg-rewrite
                "risk_level": "high_risk",  # fcg-rewrite
                "trigger_count": 3,  # fcg-rewrite
                "time_window_minutes": 10,  # fcg-rewrite
                "ban_duration_minutes": 60  # fcg-rewrite
            }
        ]
    }


@router.get("/banned-users")  # fcg-rewrite
async def get_banned_users(  # fcg-rewrite
    skip: int = Query(0, ge=0, description="Number of records to skip"),  # fcg-rewrite
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),  # fcg-rewrite
    application_id: str = Depends(get_current_application_id)  # fcg-rewrite
):
    """Get list of banned users"""
    try:
        users = await BanPolicyManager.get_banned_users(  # fcg-rewrite
            application_id,  # fcg-rewrite
            skip=skip,  # fcg-rewrite
            limit=limit  # fcg-rewrite
        )

        return {"users": users}  # fcg-rewrite

    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to get banned users: {str(e)}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to get banned users: {str(e)}")  # fcg-rewrite


@router.post("/unban")  # fcg-rewrite
async def unban_user(  # fcg-rewrite
    request: UnbanUserRequest,  # fcg-rewrite
    application_id: str = Depends(get_current_application_id)  # fcg-rewrite
):
    """Manually unban user"""
    try:
        success = await BanPolicyManager.unban_user(application_id, request.user_id)  # fcg-rewrite

        if success:  # fcg-rewrite
            return {  # fcg-rewrite
                "success": True,  # fcg-rewrite
                "message": f"User {request.user_id} has been unbanned"  # fcg-rewrite
            }
        else:
            return {  # fcg-rewrite
                "success": False,  # fcg-rewrite
                "message": f"User {request.user_id} is not banned or has already been unbanned"  # fcg-rewrite
            }

    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to unban user: {str(e)}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to unban user: {str(e)}")  # fcg-rewrite


@router.get("/user-history/{user_id}")  # fcg-rewrite
async def get_user_risk_history(  # fcg-rewrite
    user_id: str,  # fcg-rewrite
    days: int = Query(7, ge=1, le=30, description="Number of days to query"),  # fcg-rewrite
    application_id: str = Depends(get_current_application_id)  # fcg-rewrite
):
    """Get user risk trigger history"""
    try:
        history = await BanPolicyManager.get_user_risk_history(  # fcg-rewrite
            application_id,  # fcg-rewrite
            user_id,  # fcg-rewrite
            days=days  # fcg-rewrite
        )

        return {  # fcg-rewrite
            "user_id": user_id,  # fcg-rewrite
            "days": days,  # fcg-rewrite
            "total": len(history),  # fcg-rewrite
            "history": history  # fcg-rewrite
        }

    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to get user risk history: {str(e)}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to get user risk history: {str(e)}")  # fcg-rewrite


@router.get("/check-status/{user_id}")  # fcg-rewrite
async def check_user_ban_status(  # fcg-rewrite
    user_id: str,  # fcg-rewrite
    application_id: str = Depends(get_current_application_id)  # fcg-rewrite
):
    """Check user ban status"""
    try:
        ban_record = await BanPolicyManager.check_user_banned(application_id, user_id)  # fcg-rewrite

        if ban_record:  # fcg-rewrite
            return {  # fcg-rewrite
                "is_banned": True,  # fcg-rewrite
                "ban_record": ban_record  # fcg-rewrite
            }
        else:
            return {  # fcg-rewrite
                "is_banned": False,  # fcg-rewrite
                "ban_record": None  # fcg-rewrite
            }

    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to check user ban status: {str(e)}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to check user ban status: {str(e)}")  # fcg-rewrite
