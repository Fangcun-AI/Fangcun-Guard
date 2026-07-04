#!/usr/bin/env python3
"""
Management service - low concurrency management platform API
Specially handles /api/v1/* management interface requests, optimizing resource usage
"""
from fastapi import FastAPI, HTTPException, Depends, Security, Request  # fcg-rewrite
from contextlib import asynccontextmanager  # fcg-rewrite
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # fcg-rewrite
from fastapi.middleware.cors import CORSMiddleware  # fcg-rewrite
from fastapi.responses import JSONResponse  # fcg-rewrite
import uvicorn  # fcg-rewrite
import os  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.connection import get_admin_db_session, init_db, create_admin_engine  # fcg-rewrite
from admin_console.routes import (  # fcg-rewrite
    account_user_routes,  # fcg-rewrite
    appeal_config_routes,  # fcg-rewrite
    application_workspace_routes,  # fcg-rewrite
    auth_session_routes,  # fcg-rewrite
    ban_rules_routes,  # fcg-rewrite
    concurrency_metrics_routes,  # fcg-rewrite
    configuration_hub,  # fcg-rewrite
    custom_scanner_routes,  # fcg-rewrite
    data_leakage_policy_routes,  # fcg-rewrite
    data_safety_routes,  # fcg-rewrite
    gateway_policy_routes,  # fcg-rewrite
    interactive_test_routes,  # fcg-rewrite
    inspection_results,  # fcg-rewrite
    media_asset_routes,  # fcg-rewrite
    model_routing_routes,  # fcg-rewrite
    ops_sync_routes,  # fcg-rewrite
    overview_routes,  # fcg-rewrite
    package_purchase_routes,  # fcg-rewrite
    payment_gateway_routes,  # fcg-rewrite
    plugin_catalog_routes,  # fcg-rewrite
    risk_profile_routes,  # fcg-rewrite
    scanner_catalog_routes,  # fcg-rewrite
    scanner_config_routes,  # fcg-rewrite
    system_admin_routes,  # fcg-rewrite
    upstream_config_routes,  # fcg-rewrite
)
from middleware.request_identity import RequestIdentityMiddleware  # fcg-rewrite
from platform_shared.routes import billing_routes  # fcg-rewrite
from services.admin_request_identity import AdminRequestIdentityResolver  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from services.admin_service import admin_service  # fcg-rewrite

# Set security verification
security = HTTPBearer()  # fcg-rewrite

# Import concurrent control middleware
from middleware.concurrent_limit_middleware import ConcurrentLimitMiddleware  # fcg-rewrite

admin_identity_resolver = AdminRequestIdentityResolver(  # fcg-rewrite
    session_factory=get_admin_db_session,  # fcg-rewrite
    admin_service=admin_service,  # fcg-rewrite
)

# Create FastAPI application
@asynccontextmanager  # fcg-rewrite
async def console_lifespan(app: FastAPI):  # fcg-rewrite
    # Startup phase
    os.makedirs(settings.data_dir, exist_ok=True)  # fcg-rewrite
    os.makedirs(settings.log_dir, exist_ok=True)  # fcg-rewrite

    # Initialize database (management service needs full initialization)
    await init_db(minimal=False)  # fcg-rewrite

    # Start cache cleaner
    from services.cache_cleaner import cache_cleaner  # fcg-rewrite
    await cache_cleaner.start()  # fcg-rewrite

    # Start log to database service (replaces old data_sync_service)
    # This service provides better incremental processing and state persistence
    if settings.store_detection_results:  # fcg-rewrite
        from services.log_to_db_service import log_to_db_service  # fcg-rewrite
        await log_to_db_service.start()  # fcg-rewrite
        logger.info("Log to DB service started (STORE_DETECTION_RESULTS=true)")  # fcg-rewrite
    else:
        logger.info("Log to DB service disabled (STORE_DETECTION_RESULTS=false)")  # fcg-rewrite

    # Initialize plugins (async part — calls plugin.initialize())
    from plugins.manager import plugin_manager  # fcg-rewrite
    await plugin_manager.warm_up_plugins(app_context={"service": "admin"})  # fcg-rewrite

    logger.info(f"{settings.app_name} Admin Service started")  # fcg-rewrite
    logger.info(f"Data directory: {settings.data_dir}")  # fcg-rewrite
    logger.info("Admin service optimized for management operations")  # fcg-rewrite

    try:
        yield
    finally:  # fcg-rewrite
        # Shutdown phase
        from services.cache_cleaner import cache_cleaner  # fcg-rewrite
        await cache_cleaner.stop()  # fcg-rewrite
        if settings.store_detection_results:  # fcg-rewrite
            from services.log_to_db_service import log_to_db_service  # fcg-rewrite
            await log_to_db_service.stop()  # fcg-rewrite
        logger.info("Admin service shutdown completed")  # fcg-rewrite

app = FastAPI(  # fcg-rewrite
    title=f"{settings.app_name} - Admin Service",  # fcg-rewrite
    version=settings.app_version,  # fcg-rewrite
    description="FangcunGuard management service - management platform API",  # fcg-rewrite
    docs_url="/docs" if settings.debug else None,  # fcg-rewrite
    redoc_url="/redoc" if settings.debug else None,  # fcg-rewrite
    lifespan=console_lifespan,  # fcg-rewrite
)

# Add concurrent control middleware (highest priority, added last)
app.add_middleware(ConcurrentLimitMiddleware, service_type="admin", max_concurrent=settings.admin_max_concurrent_requests)  # fcg-rewrite

# Add authentication context middleware
app.add_middleware(RequestIdentityMiddleware, resolver=admin_identity_resolver)  # fcg-rewrite

# Configure CORS
app.add_middleware(  # fcg-rewrite
    CORSMiddleware,  # fcg-rewrite
    allow_origins=["*"],  # fcg-rewrite
    allow_credentials=True,  # fcg-rewrite
    allow_methods=["*"],  # fcg-rewrite
    allow_headers=["*"],  # fcg-rewrite
    expose_headers=["*"],  # fcg-rewrite
)

# Set log
logger = setup_logger()  # fcg-rewrite

@app.get("/")  # fcg-rewrite
async def admin_root_info():  # fcg-rewrite
    """Root path"""
    return {  # fcg-rewrite
        "name": f"{settings.app_name} - Admin Service",  # fcg-rewrite
        "version": settings.app_version,  # fcg-rewrite
        "status": "running",  # fcg-rewrite
        "service_type": "admin",  # fcg-rewrite
        "support_email": settings.support_email,  # fcg-rewrite
        "workers": settings.admin_uvicorn_workers  # fcg-rewrite
    }

@app.get("/health")  # fcg-rewrite
async def admin_health_probe():  # fcg-rewrite
    """Health check"""
    return {  # fcg-rewrite
        "status": "healthy",   # fcg-rewrite
        "version": settings.app_version,  # fcg-rewrite
        "service": "admin"  # fcg-rewrite
    }

# User authentication function (full version)
async def require_authenticated_context(  # fcg-rewrite
    credentials: HTTPAuthorizationCredentials = Security(security),  # fcg-rewrite
    request: Request = None,  # fcg-rewrite
):
    """Verify user authentication (management service only)"""
    if request is not None:  # fcg-rewrite
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        if request_context:  # fcg-rewrite
            return request_context  # fcg-rewrite
    raise HTTPException(status_code=401, detail="Invalid credentials")  # fcg-rewrite

# Register management routes
app.include_router(auth_session_routes.router, prefix="/api/v1/auth")  # fcg-rewrite
app.include_router(account_user_routes.router, prefix="/api/v1/users")  # fcg-rewrite
app.include_router(overview_routes.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
# Register public config routes (no auth required - e.g., system-info for deployment mode)
app.include_router(configuration_hub.public_router, prefix="/api/v1")  # fcg-rewrite
# Register protected config routes (auth required)
app.include_router(configuration_hub.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
app.include_router(inspection_results.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
app.include_router(ops_sync_routes.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
app.include_router(system_admin_routes.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
app.include_router(interactive_test_routes.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
app.include_router(upstream_config_routes.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
app.include_router(concurrency_metrics_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
# Data Security entity types management
app.include_router(data_safety_routes.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Data Leakage Policy management
app.include_router(data_leakage_policy_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Gateway Policy management (unified security policy for Security Gateway)
app.include_router(gateway_policy_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Model Routes management (automatic model routing for Security Gateway)
app.include_router(model_routing_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Billing and Payment routes (only in SaaS mode)
if settings.is_saas_mode:  # fcg-rewrite
    app.include_router(billing_routes.router, dependencies=[Depends(require_authenticated_context)])  # Billing APIs  # fcg-rewrite
    app.include_router(payment_gateway_routes.router)  # Payment API (webhook endpoints don't require auth)  # fcg-rewrite
    logger.info("Billing and payment routes enabled (SaaS mode)")  # fcg-rewrite
else:
    logger.info("Billing and payment routes disabled (enterprise mode)")  # fcg-rewrite

app.include_router(application_workspace_routes.router, prefix="/api/v1/applications", dependencies=[Depends(require_authenticated_context)])  # Application Management  # fcg-rewrite

# Scanner Package System routes
app.include_router(scanner_catalog_routes.router, dependencies=[Depends(require_authenticated_context)])  # Scanner Packages  # fcg-rewrite
app.include_router(scanner_config_routes.router, dependencies=[Depends(require_authenticated_context)])  # Scanner Configs  # fcg-rewrite
app.include_router(custom_scanner_routes.router, dependencies=[Depends(require_authenticated_context)])  # Custom Scanners  # fcg-rewrite

# Package purchase routes (only in SaaS mode for premium packages)
if settings.is_saas_mode:  # fcg-rewrite
    app.include_router(package_purchase_routes.router, dependencies=[Depends(require_authenticated_context)])  # Package Purchases  # fcg-rewrite
    logger.info("Package purchase routes enabled (SaaS mode)")  # fcg-rewrite
else:
    logger.info("Package purchase routes disabled (enterprise mode)")  # fcg-rewrite

# Import and register ban policy routes
app.include_router(ban_rules_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Import and register appeal configuration routes
app.include_router(appeal_config_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Plugin system: discover and register plugins (sync), then register their routers
from plugins.manager import plugin_manager as _pm  # fcg-rewrite
from plugins.registry import plugin_registry as _pr  # fcg-rewrite
_pm.discover_plugins()  # sync: importlib discovery only, no async calls  # fcg-rewrite
for _pname, _plugin in _pr.get_all().items():  # fcg-rewrite
    for _router in _plugin.get_routers():  # fcg-rewrite
        app.include_router(_router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Plugin management API (Tool Center)
app.include_router(plugin_catalog_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Risk configuration routes
app.include_router(risk_profile_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
# Media router: image upload/delete needs authentication, but image access does not need authentication
# First register image access routes that do not need authentication
from fastapi import APIRouter  # fcg-rewrite
from fastapi.responses import FileResponse  # fcg-rewrite
from pathlib import Path  # fcg-rewrite

public_media_router = APIRouter(tags=["Media"])  # fcg-rewrite

@public_media_router.get("/media/image/{tenant_id}/{filename}")  # fcg-rewrite
async def serve_public_image(tenant_id: str, filename: str):  # fcg-rewrite
    """Get image file (public access, no authentication)"""
    try:
        file_path = Path(settings.media_dir) / tenant_id / filename  # fcg-rewrite
        if not str(file_path).startswith(str(Path(settings.media_dir))):  # fcg-rewrite
            raise HTTPException(status_code=403, detail="No access to this file")  # fcg-rewrite
        if not file_path.exists() or not file_path.is_file():  # fcg-rewrite
            raise HTTPException(status_code=404, detail="File not found")  # fcg-rewrite
        return FileResponse(path=str(file_path), media_type="image/jpeg", filename=filename)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as e:  # fcg-rewrite
        logger.error(f"Get image error: {e}")  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"Get image failed: {str(e)}")  # fcg-rewrite

app.include_router(public_media_router, prefix="/api/v1")  # fcg-rewrite
app.include_router(media_asset_routes.router, prefix="/api/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite


# Global exception handling
@app.exception_handler(Exception)  # fcg-rewrite
async def handle_admin_exception(request, exc):  # fcg-rewrite
    import traceback  # fcg-rewrite
    logger.error(f"Admin service exception: {exc}")  # fcg-rewrite
    logger.error(f"Traceback: {traceback.format_exc()}")  # fcg-rewrite
    return JSONResponse(  # fcg-rewrite
        status_code=500,  # fcg-rewrite
        content={"detail": f"Admin service internal error: {str(exc)}"}  # fcg-rewrite
    )

if __name__ == "__main__":  # fcg-rewrite
    uvicorn.run(  # fcg-rewrite
        "admin_service:app",  # fcg-rewrite
        host=settings.host,  # fcg-rewrite
        port=settings.admin_port,  # fcg-rewrite
        reload=settings.debug,  # fcg-rewrite
        log_level=settings.log_level.lower(),  # fcg-rewrite
        workers=settings.admin_uvicorn_workers if not settings.debug else 1  # fcg-rewrite
    )
