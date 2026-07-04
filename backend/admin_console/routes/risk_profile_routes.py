from fastapi import APIRouter, Depends, HTTPException, Request  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite
from typing import Dict  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from services.risk_config_service import RiskConfigService  # fcg-rewrite
from services.risk_config_cache import risk_config_cache  # fcg-rewrite
from services.application_request_context import resolve_admin_application_context  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from pydantic import BaseModel, Field  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(prefix="/api/v1/config", tags=["Risk type configuration"])  # fcg-rewrite


def get_current_user_and_application_from_request(request: Request, db: Session):  # fcg-rewrite
    context = resolve_admin_application_context(request, db)  # fcg-rewrite
    return context.tenant, context.application_id  # fcg-rewrite

class RiskConfigRequest(BaseModel):  # fcg-rewrite
    s1_enabled: bool = True  # fcg-rewrite
    s2_enabled: bool = True  # fcg-rewrite
    s3_enabled: bool = True  # fcg-rewrite
    s4_enabled: bool = True  # fcg-rewrite
    s5_enabled: bool = True  # fcg-rewrite
    s6_enabled: bool = True  # fcg-rewrite
    s7_enabled: bool = True  # fcg-rewrite
    s8_enabled: bool = True  # fcg-rewrite
    s9_enabled: bool = True  # fcg-rewrite
    s10_enabled: bool = True  # fcg-rewrite
    s11_enabled: bool = True  # fcg-rewrite
    s12_enabled: bool = True  # fcg-rewrite
    s13_enabled: bool = True  # fcg-rewrite
    s14_enabled: bool = True  # fcg-rewrite
    s15_enabled: bool = True  # fcg-rewrite
    s16_enabled: bool = True  # fcg-rewrite
    s17_enabled: bool = True  # fcg-rewrite
    s18_enabled: bool = True  # fcg-rewrite
    s19_enabled: bool = True  # fcg-rewrite
    s20_enabled: bool = True  # fcg-rewrite
    s21_enabled: bool = True  # fcg-rewrite

class RiskConfigResponse(BaseModel):  # fcg-rewrite
    s1_enabled: bool  # fcg-rewrite
    s2_enabled: bool  # fcg-rewrite
    s3_enabled: bool  # fcg-rewrite
    s4_enabled: bool  # fcg-rewrite
    s5_enabled: bool  # fcg-rewrite
    s6_enabled: bool  # fcg-rewrite
    s7_enabled: bool  # fcg-rewrite
    s8_enabled: bool  # fcg-rewrite
    s9_enabled: bool  # fcg-rewrite
    s10_enabled: bool  # fcg-rewrite
    s11_enabled: bool  # fcg-rewrite
    s12_enabled: bool  # fcg-rewrite
    s13_enabled: bool  # fcg-rewrite
    s14_enabled: bool  # fcg-rewrite
    s15_enabled: bool  # fcg-rewrite
    s16_enabled: bool  # fcg-rewrite
    s17_enabled: bool  # fcg-rewrite
    s18_enabled: bool  # fcg-rewrite
    s19_enabled: bool  # fcg-rewrite
    s20_enabled: bool  # fcg-rewrite
    s21_enabled: bool  # fcg-rewrite

    class Config:  # fcg-rewrite
        from_attributes = True  # fcg-rewrite

class SensitivityThresholdRequest(BaseModel):  # fcg-rewrite
    high_sensitivity_threshold: float = Field(..., ge=0.0, le=1.0)  # fcg-rewrite
    medium_sensitivity_threshold: float = Field(..., ge=0.0, le=1.0)  # fcg-rewrite
    low_sensitivity_threshold: float = Field(..., ge=0.0, le=1.0)  # fcg-rewrite
    sensitivity_trigger_level: str = Field(..., pattern="^(low|medium|high)$")  # fcg-rewrite

class SensitivityThresholdResponse(BaseModel):  # fcg-rewrite
    high_sensitivity_threshold: float  # fcg-rewrite
    medium_sensitivity_threshold: float  # fcg-rewrite
    low_sensitivity_threshold: float  # fcg-rewrite
    sensitivity_trigger_level: str  # fcg-rewrite

    class Config:  # fcg-rewrite
        from_attributes = True  # fcg-rewrite

@router.get("/risk-types", response_model=RiskConfigResponse)  # fcg-rewrite
async def get_risk_config(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """Get application risk type configuration"""
    try:
        current_user, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
        risk_service = RiskConfigService(db)  # fcg-rewrite
        config_dict = risk_service.get_risk_config_dict(application_id=str(application_id))  # fcg-rewrite
        return RiskConfigResponse(**config_dict)  # fcg-rewrite
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to get risk config: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to get risk config")  # fcg-rewrite

@router.put("/risk-types", response_model=RiskConfigResponse)  # fcg-rewrite
async def update_risk_config(  # fcg-rewrite
    config_request: RiskConfigRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """Update application risk type configuration"""
    try:
        current_user, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
        risk_service = RiskConfigService(db)  # fcg-rewrite
        config_data = config_request.dict()  # fcg-rewrite

        updated_config = risk_service.update_risk_config(application_id=str(application_id), config_data=config_data)  # fcg-rewrite
        if not updated_config:  # fcg-rewrite
            raise HTTPException(status_code=500, detail="Failed to update risk config")  # fcg-rewrite

        # Clear the application's cache, force reload
        await risk_config_cache.invalidate_user_cache(application_id=str(application_id))  # fcg-rewrite

        # Return updated configuration
        config_dict = risk_service.get_risk_config_dict(application_id=str(application_id))  # fcg-rewrite
        logger.info(f"Updated risk config for application {application_id}")  # fcg-rewrite

        return RiskConfigResponse(**config_dict)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to update risk config: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to update risk config")  # fcg-rewrite

@router.get("/risk-types/enabled", response_model=Dict[str, bool])  # fcg-rewrite
async def get_enabled_risk_types(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """Get application enabled risk type mapping"""
    try:
        current_user, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
        risk_service = RiskConfigService(db)  # fcg-rewrite
        enabled_types = risk_service.get_enabled_risk_types(application_id=str(application_id))  # fcg-rewrite
        return enabled_types  # fcg-rewrite
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to get enabled risk types: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to get enabled risk types")  # fcg-rewrite

@router.post("/risk-types/reset")  # fcg-rewrite
async def reset_risk_config(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """Reset risk type configuration to default (all enabled)"""
    try:
        current_user, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
        risk_service = RiskConfigService(db)  # fcg-rewrite
        default_config = {  # fcg-rewrite
            's1_enabled': True, 's2_enabled': True, 's3_enabled': True, 's4_enabled': True,  # fcg-rewrite
            's5_enabled': True, 's6_enabled': True, 's7_enabled': True, 's8_enabled': True,  # fcg-rewrite
            's9_enabled': True, 's10_enabled': True, 's11_enabled': True, 's12_enabled': True,  # fcg-rewrite
            's13_enabled': True, 's14_enabled': True, 's15_enabled': True, 's16_enabled': True,  # fcg-rewrite
            's17_enabled': True, 's18_enabled': True, 's19_enabled': True, 's20_enabled': True,  # fcg-rewrite
            's21_enabled': True  # fcg-rewrite
        }

        updated_config = risk_service.update_risk_config(application_id=str(application_id), config_data=default_config)  # fcg-rewrite
        if not updated_config:  # fcg-rewrite
            raise HTTPException(status_code=500, detail="Failed to reset risk config")  # fcg-rewrite

        # Clear the application's cache
        await risk_config_cache.invalidate_user_cache(application_id=str(application_id))  # fcg-rewrite

        logger.info(f"Reset risk config to default for application {application_id}")  # fcg-rewrite
        return {"message": "Risk config has been reset to default"}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to reset risk config: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to reset risk config")  # fcg-rewrite

@router.get("/sensitivity-thresholds", response_model=SensitivityThresholdResponse)  # fcg-rewrite
async def get_sensitivity_thresholds(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """Get application sensitivity threshold configuration"""
    try:
        current_user, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
        risk_service = RiskConfigService(db)  # fcg-rewrite
        config_dict = risk_service.get_sensitivity_threshold_dict(application_id=str(application_id))  # fcg-rewrite
        return SensitivityThresholdResponse(**config_dict)  # fcg-rewrite
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to get sensitivity thresholds: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to get sensitivity thresholds")  # fcg-rewrite

@router.put("/sensitivity-thresholds", response_model=SensitivityThresholdResponse)  # fcg-rewrite
async def update_sensitivity_thresholds(  # fcg-rewrite
    threshold_request: SensitivityThresholdRequest,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """Update application sensitivity threshold configuration"""
    try:
        current_user, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
        risk_service = RiskConfigService(db)  # fcg-rewrite
        threshold_data = threshold_request.dict()  # fcg-rewrite

        updated_config = risk_service.update_sensitivity_thresholds(application_id=str(application_id), threshold_data=threshold_data)  # fcg-rewrite
        if not updated_config:  # fcg-rewrite
            raise HTTPException(status_code=500, detail="Failed to update sensitivity thresholds")  # fcg-rewrite

        # Clear the application's sensitivity cache, force reload
        await risk_config_cache.invalidate_sensitivity_cache(application_id=str(application_id))  # fcg-rewrite

        # Return updated configuration
        config_dict = risk_service.get_sensitivity_threshold_dict(application_id=str(application_id))  # fcg-rewrite
        logger.info(f"Updated sensitivity thresholds for application {application_id}")  # fcg-rewrite

        return SensitivityThresholdResponse(**config_dict)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to update sensitivity thresholds: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to update sensitivity thresholds")  # fcg-rewrite

@router.post("/sensitivity-thresholds/reset")  # fcg-rewrite
async def reset_sensitivity_thresholds(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    """Reset sensitivity threshold configuration to default"""
    try:
        current_user, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
        risk_service = RiskConfigService(db)  # fcg-rewrite
        default_config = {  # fcg-rewrite
            'high_sensitivity_threshold': 0.40,  # fcg-rewrite
            'medium_sensitivity_threshold': 0.60,  # fcg-rewrite
            'low_sensitivity_threshold': 0.95,  # fcg-rewrite
            'sensitivity_trigger_level': 'medium'  # fcg-rewrite
        }

        updated_config = risk_service.update_sensitivity_thresholds(application_id=str(application_id), threshold_data=default_config)  # fcg-rewrite
        if not updated_config:  # fcg-rewrite
            raise HTTPException(status_code=500, detail="Failed to reset sensitivity thresholds")  # fcg-rewrite

        # Clear the application's sensitivity cache
        await risk_config_cache.invalidate_sensitivity_cache(application_id=str(application_id))  # fcg-rewrite

        logger.info(f"Reset sensitivity thresholds to default for application {application_id}")  # fcg-rewrite
        return {"message": "Sensitivity thresholds have been reset to default"}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to reset sensitivity thresholds: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to reset sensitivity thresholds")  # fcg-rewrite
