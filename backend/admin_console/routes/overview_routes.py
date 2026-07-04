from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from database.connection import get_admin_db
from services.stats_service import StatsService
from services.application_request_context import resolve_tenant_application_context
from models.responses import DashboardStats
from utils.logger import setup_logger
from config import settings
from typing import Optional

logger = setup_logger()
router = APIRouter(tags=["Dashboard"])

def get_current_user_and_application_from_request(request: Request, db: Session):
    context = resolve_tenant_application_context(request, db)
    return context.tenant, context.application_id

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(request: Request, db: Session = Depends(get_admin_db)):
    """Get dashboard stats"""
    try:
        # Get user and application context
        current_user, application_id = get_current_user_and_application_from_request(request, db)

        stats_service = StatsService(db)
        stats = stats_service.get_dashboard_stats(application_id=application_id)

        logger.info(f"Dashboard stats retrieved successfully for user {current_user.id} and application {application_id}")
        return DashboardStats(**stats)

    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard stats")

@router.get("/dashboard/category-distribution")
async def get_category_distribution(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_admin_db)
):
    """Get risk category distribution stats"""
    try:
        # Get user and application context
        current_user, application_id = get_current_user_and_application_from_request(request, db)

        stats_service = StatsService(db)
        category_data = stats_service.get_category_distribution(start_date, end_date, application_id=application_id)

        logger.info(f"Category distribution retrieved successfully for user {current_user.id} and application {application_id}")
        return {"categories": category_data}

    except Exception as e:
        logger.error(f"Category distribution error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get category distribution")
