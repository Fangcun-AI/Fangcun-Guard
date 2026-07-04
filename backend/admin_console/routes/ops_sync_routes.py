from fastapi import APIRouter, HTTPException, Query  # fcg-rewrite
from typing import Optional  # fcg-rewrite
from datetime import datetime, date  # fcg-rewrite
from services.log_to_db_service import log_to_db_service  # fcg-rewrite
from services.async_logger import async_detection_logger  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from config import settings  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Data Sync"])  # fcg-rewrite

@router.post("/sync/force")  # fcg-rewrite
async def force_sync_data(  # fcg-rewrite
    start_date: Optional[str] = Query(None, description="Start date (YYYYMMDD)"),  # fcg-rewrite
    end_date: Optional[str] = Query(None, description="End date (YYYYMMDD)")  # fcg-rewrite
):
    """
    Force sync log data to database

    Args:
        start_date: Start date, format YYYYMMDD
        end_date: End date, format YYYYMMDD
    """
    # Check if log to DB service is enabled
    if not settings.store_detection_results:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=400,  # fcg-rewrite
            detail="Log to DB service is disabled. Set STORE_DETECTION_RESULTS=true to enable."  # fcg-rewrite
        )

    try:
        date_range = None  # fcg-rewrite
        if start_date and end_date:  # fcg-rewrite
            # Validate date format
            try:
                datetime.strptime(start_date, '%Y%m%d')  # fcg-rewrite
                datetime.strptime(end_date, '%Y%m%d')  # fcg-rewrite
                date_range = (start_date, end_date)  # fcg-rewrite
            except ValueError:  # fcg-rewrite
                raise HTTPException(status_code=400, detail="Date format error, please use YYYYMMDD format")  # fcg-rewrite

        # Execute force sync
        await log_to_db_service.force_sync(date_range)  # fcg-rewrite

        return {  # fcg-rewrite
            "status": "success",  # fcg-rewrite
            "message": "Data sync completed",  # fcg-rewrite
            "date_range": date_range,  # fcg-rewrite
            "timestamp": datetime.now().isoformat()  # fcg-rewrite
        }

    except Exception as e:  # fcg-rewrite
        logger.error(f"Force sync failed: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")  # fcg-rewrite

@router.get("/sync/status")  # fcg-rewrite
async def get_sync_status():  # fcg-rewrite
    """
    Get data sync service status
    """
    try:
        from pathlib import Path  # fcg-rewrite

        # Get log file information
        detection_log_dir = Path(settings.detection_log_dir)  # fcg-rewrite
        log_files = sorted(detection_log_dir.glob("detection_*.jsonl")) if detection_log_dir.exists() else []  # fcg-rewrite

        # Count log file information
        file_info = []  # fcg-rewrite
        for log_file in log_files[-5:]:  # Only show the last 5 files  # fcg-rewrite
            try:
                stat = log_file.stat()  # fcg-rewrite
                processed_lines = log_to_db_service.processed_files.get(log_file.name, 0)  # fcg-rewrite
                file_info.append({  # fcg-rewrite
                    "filename": log_file.name,  # fcg-rewrite
                    "size_bytes": stat.st_size,  # fcg-rewrite
                    "processed_lines": processed_lines,  # fcg-rewrite
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat()  # fcg-rewrite
                })
            except:
                continue  # fcg-rewrite

        return {  # fcg-rewrite
            "sync_service_running": log_to_db_service.running,  # fcg-rewrite
            "sync_service_enabled": settings.store_detection_results,  # fcg-rewrite
            "async_logger_running": async_detection_logger._running,  # fcg-rewrite
            "total_files_processed": len(log_to_db_service.processed_files),  # fcg-rewrite
            "total_lines_processed": sum(log_to_db_service.processed_files.values()),  # fcg-rewrite
            "recent_log_files": file_info,  # fcg-rewrite
            "timestamp": datetime.now().isoformat()  # fcg-rewrite
        }

    except Exception as e:  # fcg-rewrite
        logger.error(f"Get sync status failed: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")  # fcg-rewrite

@router.post("/sync/restart")  # fcg-rewrite
async def restart_sync_service():  # fcg-rewrite
    """
    Restart data sync service
    """
    # Check if log to DB service is enabled
    if not settings.store_detection_results:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=400,  # fcg-rewrite
            detail="Log to DB service is disabled. Set STORE_DETECTION_RESULTS=true to enable."  # fcg-rewrite
        )

    try:
        # Stop services
        await log_to_db_service.stop()  # fcg-rewrite
        await async_detection_logger.stop()  # fcg-rewrite

        # Start services
        await async_detection_logger.start()  # fcg-rewrite
        await log_to_db_service.start()  # fcg-rewrite

        return {  # fcg-rewrite
            "status": "success",  # fcg-rewrite
            "message": "Data sync service restarted",  # fcg-rewrite
            "timestamp": datetime.now().isoformat()  # fcg-rewrite
        }

    except Exception as e:  # fcg-rewrite
        logger.error(f"Restart sync service failed: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Restart failed: {str(e)}")  # fcg-rewrite
