#!/usr/bin/env python3
"""
Detection service - high-concurrency guardrail detection API
Specialized for /v1/guardrails detection requests, optimized for high concurrency performance
"""
from fastapi import FastAPI, HTTPException, Depends, Security, Request  # fcg-rewrite
from contextlib import asynccontextmanager  # fcg-rewrite
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # fcg-rewrite
from fastapi.middleware.cors import CORSMiddleware  # fcg-rewrite
from fastapi.responses import JSONResponse  # fcg-rewrite
import uvicorn  # fcg-rewrite
import os  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.connection import get_detection_db_session, init_db, create_detection_engine  # fcg-rewrite
from guard_runtime.routes import content_scan_routes, detection_api_routes, dify_extension_routes  # fcg-rewrite
from middleware.request_identity import RequestIdentityMiddleware  # fcg-rewrite
from platform_shared.routes import appeal_public_routes, billing_routes, direct_model_routes  # fcg-rewrite
from services.async_logger import async_detection_logger  # fcg-rewrite
from services.request_identity_service import RequestIdentityPolicy, RequestIdentityResolver  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

# Set security verification (auto_error=False to allow manual handling)
security = HTTPBearer(auto_error=False)  # fcg-rewrite

# Import concurrent control middleware
from middleware.concurrent_limit_middleware import ConcurrentLimitMiddleware  # fcg-rewrite

detection_identity_resolver = RequestIdentityResolver(  # fcg-rewrite
    session_factory=get_detection_db_session,  # fcg-rewrite
    policy=RequestIdentityPolicy(  # fcg-rewrite
        route_prefixes=("/v1/guardrails", "/v1/dify", "/v1/scan/"),  # fcg-rewrite
        allow_direct_api_keys=False,  # fcg-rewrite
        require_tenant_record_for_jwt=True,  # fcg-rewrite
    ),
    service_name="detection",  # fcg-rewrite
)

# Create FastAPI application
@asynccontextmanager  # fcg-rewrite
async def detection_lifespan_handler(app: FastAPI):  # fcg-rewrite
    # Startup phase
    os.makedirs(settings.data_dir, exist_ok=True)  # fcg-rewrite
    os.makedirs(settings.log_dir, exist_ok=True)  # fcg-rewrite
    os.makedirs(settings.detection_log_dir, exist_ok=True)  # fcg-rewrite

    # Initialize database (detection service does not need full initialization)
    await init_db(minimal=True)  # fcg-rewrite

    # Start asynchronous logging service
    await async_detection_logger.start()  # fcg-rewrite

    # Initialize plugin system (detection service uses dispatch_hook for detection phase)
    from plugins.manager import plugin_manager  # fcg-rewrite
    await plugin_manager.bootstrap_plugins(app=None, app_context={"service": "detection"})  # fcg-rewrite

    logger.info(f"{settings.app_name} Detection Service started")  # fcg-rewrite
    logger.info(f"Detection API URL: {settings.guardrails_model_api_url}")  # fcg-rewrite
    logger.info("Detection service optimized for high concurrency")  # fcg-rewrite
    
    try:
        yield
    finally:  # fcg-rewrite
        # Shutdown phase
        await async_detection_logger.stop()  # fcg-rewrite
        from services.model_service import model_service  # fcg-rewrite
        await model_service.close()  # fcg-rewrite
        logger.info("Detection service shutdown completed")  # fcg-rewrite

app = FastAPI(  # fcg-rewrite
    title=f"{settings.app_name} - Detection Service",  # fcg-rewrite
    version=settings.app_version,  # fcg-rewrite
    description="FangcunGuard detection service - high-concurrency detection API",  # fcg-rewrite
    docs_url="/docs" if settings.debug else None,  # fcg-rewrite
    redoc_url="/redoc" if settings.debug else None,  # fcg-rewrite
    lifespan=detection_lifespan_handler,  # fcg-rewrite
)

# Add concurrent control middleware (highest priority, added last)
app.add_middleware(ConcurrentLimitMiddleware, service_type="detection", max_concurrent=settings.detection_max_concurrent_requests)  # fcg-rewrite

# Add rate limit middleware (RPS limiting)
from middleware.rate_limit_middleware import RateLimitMiddleware  # fcg-rewrite
app.add_middleware(RateLimitMiddleware)  # fcg-rewrite

# Add billing middleware (monthly quota limiting)
from middleware.billing_middleware import BillingMiddleware  # fcg-rewrite
app.add_middleware(BillingMiddleware)  # fcg-rewrite

# Add authentication context middleware
app.add_middleware(RequestIdentityMiddleware, resolver=detection_identity_resolver)  # fcg-rewrite

# Configure CORS
app.add_middleware(  # fcg-rewrite
    CORSMiddleware,  # fcg-rewrite
    allow_origins=["*"],  # fcg-rewrite
    allow_credentials=True,  # fcg-rewrite
    allow_methods=["GET", "POST"],  # fcg-rewrite
    allow_headers=["*"],  # fcg-rewrite
)

# Set log
logger = setup_logger()  # fcg-rewrite

@app.get("/")  # fcg-rewrite
async def detection_root_info():  # fcg-rewrite
    """Root path"""
    return {  # fcg-rewrite
        "name": f"{settings.app_name} - Detection Service",  # fcg-rewrite
        "version": settings.app_version,  # fcg-rewrite
        "status": "running",  # fcg-rewrite
        "service_type": "detection",  # fcg-rewrite
        "model_api_url": settings.guardrails_model_api_url,  # fcg-rewrite
        "workers": settings.detection_uvicorn_workers,  # fcg-rewrite
        "max_concurrent": settings.detection_max_concurrent_requests  # fcg-rewrite
    }

@app.get("/health")  # fcg-rewrite
async def detection_health_probe():  # fcg-rewrite
    """Health check"""
    return {  # fcg-rewrite
        "status": "healthy",  # fcg-rewrite
        "version": settings.app_version,  # fcg-rewrite
        "service": "detection"  # fcg-rewrite
    }

@app.get("/metrics")  # fcg-rewrite
async def render_detection_metrics():  # fcg-rewrite
    """Prometheus-compatible metrics endpoint"""
    from services.model_service import model_service  # fcg-rewrite
    cb = model_service._circuit_breaker  # fcg-rewrite
    lines = [  # fcg-rewrite
        '# HELP model_circuit_breaker_state Circuit breaker state (0=closed, 1=open)',  # fcg-rewrite
        f'model_circuit_breaker_state {1 if cb.is_open else 0}',  # fcg-rewrite
        '# HELP model_circuit_breaker_failures Consecutive failure count',  # fcg-rewrite
        f'model_circuit_breaker_failures {cb._failure_count}',  # fcg-rewrite
        '# HELP detection_service_info Service info',  # fcg-rewrite
        f'detection_service_info{{version="{settings.app_version}",workers="{settings.detection_uvicorn_workers}"}} 1',  # fcg-rewrite
    ]
    from starlette.responses import Response  # fcg-rewrite
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; charset=utf-8")  # fcg-rewrite

# User authentication function (simplified version)
async def require_authenticated_context(  # fcg-rewrite
    credentials: HTTPAuthorizationCredentials = Security(security),  # fcg-rewrite
    request: Request = None,  # fcg-rewrite
):
    """Verify user authentication (detection service专用)"""
    # Use middleware parsed authentication context
    if request is not None:  # fcg-rewrite
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        if request_context:  # fcg-rewrite
            return request_context  # fcg-rewrite

    # If middleware didn't set auth_context, check if it's because of missing/invalid auth
    raise HTTPException(status_code=401, detail="Not authenticated")  # fcg-rewrite

# Register detection routes (special version)
app.include_router(detection_api_routes.router, prefix="/v1", dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite
app.include_router(dify_extension_routes.router, prefix="/v1", dependencies=[Depends(require_authenticated_context)])  # Dify API-based Extension  # fcg-rewrite
app.include_router(billing_routes.router, dependencies=[Depends(require_authenticated_context)])  # Billing APIs  # fcg-rewrite
app.include_router(content_scan_routes.router, prefix="/v1", dependencies=[Depends(require_authenticated_context)])  # Content Scan APIs  # fcg-rewrite

# Register direct model access routes (uses its own auth and does not depend on the shared request-context guard)
app.include_router(direct_model_routes.router, prefix="/v1")  # Direct Model Access (auth handled internally)  # fcg-rewrite

# Register appeal routes (public endpoint, no authentication required)
app.include_router(appeal_public_routes.router)  # Appeal processing (public URL contains request_id as token)  # fcg-rewrite

# Global exception handling
@app.exception_handler(Exception)  # fcg-rewrite
async def handle_detection_exception(request, exc):  # fcg-rewrite
    logger.error(f"Detection service exception: {exc}")  # fcg-rewrite
    return JSONResponse(  # fcg-rewrite
        status_code=500,  # fcg-rewrite
        content={"detail": "Detection service internal error"}  # fcg-rewrite
    )

if __name__ == "__main__":  # fcg-rewrite
    uvicorn.run(  # fcg-rewrite
        "detection_service:app",  # fcg-rewrite
        host=settings.host,  # fcg-rewrite
        port=settings.detection_port,  # fcg-rewrite
        reload=settings.debug,  # fcg-rewrite
        log_level=settings.log_level.lower(),  # fcg-rewrite
        workers=settings.detection_uvicorn_workers if not settings.debug else 1  # fcg-rewrite
    )
