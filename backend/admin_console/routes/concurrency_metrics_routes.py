"""
Concurrent stats API - Admin view concurrent stats for all services
"""
from fastapi import APIRouter, Depends, HTTPException  # fcg-rewrite
from typing import Dict, Any  # fcg-rewrite
import asyncio  # fcg-rewrite

from middleware.concurrent_limit_middleware import ConcurrentLimitMiddleware  # fcg-rewrite
from admin_console.routes.auth_session_routes import get_current_admin  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

router = APIRouter(prefix="/api/v1/concurrent", tags=["Concurrent stats"])  # fcg-rewrite
logger = setup_logger()  # fcg-rewrite

@router.get("/stats", summary="Get concurrent stats for all services")  # fcg-rewrite
async def get_concurrent_stats(admin_user=Depends(get_current_admin)) -> Dict[str, Any]:  # fcg-rewrite
    """
    Get concurrent stats for all services
    Only admin can access this API
    """
    try:
        # Get concurrent stats for all services
        all_stats = ConcurrentLimitMiddleware.get_all_stats()  # fcg-rewrite
        
        # Build return data
        result = {  # fcg-rewrite
            "services": {},  # fcg-rewrite
            "summary": {  # fcg-rewrite
                "total_services": len(all_stats),  # fcg-rewrite
                "total_current_requests": 0,  # fcg-rewrite
                "total_processed_requests": 0,  # fcg-rewrite
                "total_rejected_requests": 0  # fcg-rewrite
            }
        }
        
        for service_type, stats in all_stats.items():  # fcg-rewrite
            result["services"][service_type] = {  # fcg-rewrite
                "current_requests": stats["current_requests"],  # fcg-rewrite
                "total_requests": stats["total_requests"],  # fcg-rewrite
                "rejected_requests": stats["rejected_requests"],  # fcg-rewrite
                "max_concurrent_reached": stats["max_concurrent_reached"],  # fcg-rewrite
                "success_rate": (stats["total_requests"] - stats["rejected_requests"]) / max(stats["total_requests"], 1) * 100,  # fcg-rewrite
                "rejection_rate": stats["rejected_requests"] / max(stats["total_requests"], 1) * 100  # fcg-rewrite
            }
            
            # Accumulate stats
            result["summary"]["total_current_requests"] += stats["current_requests"]  # fcg-rewrite
            result["summary"]["total_processed_requests"] += stats["total_requests"]  # fcg-rewrite
            result["summary"]["total_rejected_requests"] += stats["rejected_requests"]  # fcg-rewrite
        
        # Calculate overall success rate
        total_requests = result["summary"]["total_processed_requests"]  # fcg-rewrite
        if total_requests > 0:  # fcg-rewrite
            result["summary"]["overall_success_rate"] = (total_requests - result["summary"]["total_rejected_requests"]) / total_requests * 100  # fcg-rewrite
        else:
            result["summary"]["overall_success_rate"] = 100.0  # fcg-rewrite
        
        return result  # fcg-rewrite
        
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to get concurrent stats: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to get concurrent statistics")  # fcg-rewrite

@router.get("/stats/{service_type}", summary="Get concurrent stats for specified service")  # fcg-rewrite
async def get_service_concurrent_stats(  # fcg-rewrite
    service_type: str,   # fcg-rewrite
    admin_user=Depends(get_current_admin)  # fcg-rewrite
) -> Dict[str, Any]:  # fcg-rewrite
    """
    Get concurrent stats for specified service
    
    Args:
        service_type: Service type (admin/detection/proxy)
    """
    try:
        if service_type not in ["admin", "detection", "proxy"]:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Invalid service type. Must be one of: admin, detection, proxy")  # fcg-rewrite
        
        stats = ConcurrentLimitMiddleware.get_stats(service_type)  # fcg-rewrite
        
        if stats is None:  # fcg-rewrite
            raise HTTPException(status_code=404, detail=f"No statistics found for service: {service_type}")  # fcg-rewrite
        
        # Build detailed stats
        result = {  # fcg-rewrite
            "service_type": service_type,  # fcg-rewrite
            "current_requests": stats["current_requests"],  # fcg-rewrite
            "total_requests": stats["total_requests"],  # fcg-rewrite
            "rejected_requests": stats["rejected_requests"],  # fcg-rewrite
            "max_concurrent_reached": stats["max_concurrent_reached"],  # fcg-rewrite
            "success_rate": (stats["total_requests"] - stats["rejected_requests"]) / max(stats["total_requests"], 1) * 100,  # fcg-rewrite
            "rejection_rate": stats["rejected_requests"] / max(stats["total_requests"], 1) * 100,  # fcg-rewrite
            "status": "healthy" if stats["rejection_rate"] < 5 else "warning" if stats["rejection_rate"] < 15 else "critical"  # fcg-rewrite
        }
        
        return result  # fcg-rewrite
        
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to get stats for {service_type}: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to get statistics for {service_type}")  # fcg-rewrite

@router.post("/stats/reset", summary="Reset concurrent stats")  # fcg-rewrite
async def reset_concurrent_stats(admin_user=Depends(get_current_admin)) -> Dict[str, str]:  # fcg-rewrite
    """
    Reset concurrent stats for all services
    Only admin can execute this operation
    """
    try:
        ConcurrentLimitMiddleware.reset_stats()  # fcg-rewrite
        logger.info(f"Concurrent statistics reset by admin: {admin_user.get('email', 'unknown')}")  # fcg-rewrite
        
        return {  # fcg-rewrite
            "message": "All concurrent statistics have been reset successfully",  # fcg-rewrite
            "reset_by": admin_user.get("email", "unknown"),  # fcg-rewrite
            "services_reset": ["admin", "detection", "proxy"]  # fcg-rewrite
        }
        
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to reset concurrent stats: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to reset concurrent statistics")  # fcg-rewrite

@router.post("/stats/{service_type}/reset", summary="Reset concurrent stats for specified service")  # fcg-rewrite
async def reset_service_concurrent_stats(  # fcg-rewrite
    service_type: str,  # fcg-rewrite
    admin_user=Depends(get_current_admin)  # fcg-rewrite
) -> Dict[str, str]:  # fcg-rewrite
    """
    Reset concurrent stats for specified service
    
    Args:
        service_type: Service type (admin/detection/proxy)
    """
    try:
        if service_type not in ["admin", "detection", "proxy"]:  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Invalid service type. Must be one of: admin, detection, proxy")  # fcg-rewrite
        
        ConcurrentLimitMiddleware.reset_stats(service_type)  # fcg-rewrite
        logger.info(f"Concurrent statistics reset for {service_type} by admin: {admin_user.get('email', 'unknown')}")  # fcg-rewrite
        
        return {  # fcg-rewrite
            "message": f"Concurrent statistics for {service_type} service have been reset successfully",  # fcg-rewrite
            "reset_by": admin_user.get("email", "unknown"),  # fcg-rewrite
            "service": service_type  # fcg-rewrite
        }
        
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to reset stats for {service_type}: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to reset statistics for {service_type}")  # fcg-rewrite

@router.get("/health", summary="Concurrent health check")  # fcg-rewrite
async def concurrent_health_probe() -> Dict[str, Any]:  # fcg-rewrite
    """
    Check concurrent health status for all services
    No admin permission, used for monitoring
    """
    try:
        all_stats = ConcurrentLimitMiddleware.get_all_stats()  # fcg-rewrite
        
        health_status = {  # fcg-rewrite
            "overall_status": "healthy",  # fcg-rewrite
            "services": {},  # fcg-rewrite
            "issues": []  # fcg-rewrite
        }
        
        for service_type, stats in all_stats.items():  # fcg-rewrite
            rejection_rate = stats["rejected_requests"] / max(stats["total_requests"], 1) * 100  # fcg-rewrite
            
            if rejection_rate >= 15:  # fcg-rewrite
                status = "critical"  # fcg-rewrite
                health_status["overall_status"] = "critical"  # fcg-rewrite
                health_status["issues"].append(f"{service_type} service has high rejection rate: {rejection_rate:.1f}%")  # fcg-rewrite
            elif rejection_rate >= 5:  # fcg-rewrite
                status = "warning"  # fcg-rewrite
                if health_status["overall_status"] == "healthy":  # fcg-rewrite
                    health_status["overall_status"] = "warning"  # fcg-rewrite
                health_status["issues"].append(f"{service_type} service has elevated rejection rate: {rejection_rate:.1f}%")  # fcg-rewrite
            else:
                status = "healthy"  # fcg-rewrite
            
            health_status["services"][service_type] = {  # fcg-rewrite
                "status": status,  # fcg-rewrite
                "current_requests": stats["current_requests"],  # fcg-rewrite
                "rejection_rate": rejection_rate,  # fcg-rewrite
                "max_concurrent_reached": stats["max_concurrent_reached"]  # fcg-rewrite
            }
        
        return health_status  # fcg-rewrite
        
    except Exception as e:  # fcg-rewrite
        logger.error(f"Failed to check concurrent health: {e}")  # fcg-rewrite
        return {  # fcg-rewrite
            "overall_status": "error",  # fcg-rewrite
            "services": {},  # fcg-rewrite
            "issues": [f"Failed to retrieve health status: {str(e)}"]  # fcg-rewrite
        }
