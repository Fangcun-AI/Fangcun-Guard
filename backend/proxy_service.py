#!/usr/bin/env python3
"""
Reverse proxy service - OpenAI compatible proxy guardrails service
Provide complete OpenAI API compatible layer, support multi-model configuration and security detection
"""
from fastapi import FastAPI, HTTPException, Depends, Security, Request  # fcg-rewrite
from contextlib import asynccontextmanager  # fcg-rewrite
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # fcg-rewrite
from fastapi.middleware.cors import CORSMiddleware  # fcg-rewrite
from fastapi.responses import JSONResponse  # fcg-rewrite
from starlette.middleware.gzip import GZipMiddleware  # fcg-rewrite
import uvicorn  # fcg-rewrite
import os  # fcg-rewrite

from config import settings  # fcg-rewrite
# Import complete proxy service implementation
from database.connection import get_admin_db_session  # fcg-rewrite
from middleware.request_identity import RequestIdentityMiddleware  # fcg-rewrite
from openai_edge.routes import gateway_bridge_routes, openai_compat_routes  # fcg-rewrite
from platform_shared.routes import direct_model_routes  # fcg-rewrite
from services.async_logger import async_detection_logger  # fcg-rewrite
from services.request_identity_service import RequestIdentityPolicy, RequestIdentityResolver  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

# Set security verification (auto_error=False to allow manual handling)
security = HTTPBearer(auto_error=False)  # fcg-rewrite

# Import concurrent control middleware
from middleware.concurrent_limit_middleware import ConcurrentLimitMiddleware  # fcg-rewrite

proxy_identity_resolver = RequestIdentityResolver(  # fcg-rewrite
    session_factory=get_admin_db_session,  # fcg-rewrite
    policy=RequestIdentityPolicy(  # fcg-rewrite
        route_prefixes=("/v1/",),  # fcg-rewrite
        allow_direct_api_keys=True,  # fcg-rewrite
    ),
    service_name="proxy",  # fcg-rewrite
)

# Create FastAPI application
@asynccontextmanager  # fcg-rewrite
async def proxy_service_lifespan(app: FastAPI):  # fcg-rewrite
    # Startup phase
    os.makedirs(settings.data_dir, exist_ok=True)  # fcg-rewrite
    os.makedirs(settings.log_dir, exist_ok=True)  # fcg-rewrite
    os.makedirs(settings.detection_log_dir, exist_ok=True)  # fcg-rewrite

    # Proxy service does not initialize database, focus on high concurrency proxy functionality

    # Start asynchronous log service
    await async_detection_logger.start()  # fcg-rewrite

    # Initialize plugin system (proxy service uses dispatch_hook for input/output/stream_complete phases)
    from plugins.manager import plugin_manager  # fcg-rewrite
    await plugin_manager.bootstrap_plugins(app=None, app_context={"service": "proxy"})  # fcg-rewrite

    logger.info(f"{settings.app_name} Proxy Service started")  # fcg-rewrite
    logger.info(f"Proxy API running on port {settings.proxy_port}")  # fcg-rewrite
    logger.info("OpenAI-compatible proxy service with guardrails protection")  # fcg-rewrite
    
    try:
        yield
    finally:  # fcg-rewrite
        # Shutdown phase
        await async_detection_logger.stop()  # fcg-rewrite
        from services.model_service import model_service  # fcg-rewrite
        await model_service.close()  # fcg-rewrite
        
        # Close HTTP client connection pool
        from services.proxy_service import proxy_service  # fcg-rewrite
        await proxy_service.close()  # fcg-rewrite
        
        logger.info("Proxy service shutdown completed")  # fcg-rewrite

app = FastAPI(  # fcg-rewrite
    title=f"{settings.app_name} - Proxy Service",  # fcg-rewrite
    version=settings.app_version,  # fcg-rewrite
    description="FangcunGuard proxy service - OpenAI compatible reverse proxy",  # fcg-rewrite
    docs_url="/docs" if settings.debug else None,  # fcg-rewrite
    redoc_url="/redoc" if settings.debug else None,  # fcg-rewrite
    lifespan=proxy_service_lifespan,  # fcg-rewrite
)

# Add concurrent control middleware (highest priority, last added)
app.add_middleware(ConcurrentLimitMiddleware, service_type="proxy", max_concurrent=settings.proxy_max_concurrent_requests)  # fcg-rewrite

# Performance optimization middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)  # fcg-rewrite

# Add rate limiting middleware
from middleware.rate_limit_middleware import RateLimitMiddleware    # fcg-rewrite
app.add_middleware(RateLimitMiddleware)  # fcg-rewrite

# Add authentication context middleware
app.add_middleware(RequestIdentityMiddleware, resolver=proxy_identity_resolver)  # fcg-rewrite

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
async def proxy_root_info():  # fcg-rewrite
    """Root path"""
    return {  # fcg-rewrite
        "name": f"{settings.app_name} - Proxy Service",  # fcg-rewrite
        "version": settings.app_version,  # fcg-rewrite
        "status": "running",  # fcg-rewrite
        "service_type": "proxy",  # fcg-rewrite
        "api_compatibility": "OpenAI v1",  # fcg-rewrite
        "supported_endpoints": [  # fcg-rewrite
            "POST /v1/chat/completions",  # fcg-rewrite
            "POST /v1/completions",   # fcg-rewrite
            "GET /v1/models",  # fcg-rewrite
            "POST /v1/model/chat/completions",  # fcg-rewrite
            "POST /v1/model/embeddings"  # fcg-rewrite
        ],
        "base_url": f"http://localhost:{settings.proxy_port}",  # fcg-rewrite
        "workers": settings.proxy_uvicorn_workers,  # fcg-rewrite
        "max_concurrent": settings.proxy_max_concurrent_requests  # fcg-rewrite
    }

@app.get("/health")  # fcg-rewrite
async def proxy_healthcheck():  # fcg-rewrite
    """Health check"""
    return {  # fcg-rewrite
        "status": "healthy",   # fcg-rewrite
        "version": settings.app_version,  # fcg-rewrite
        "service": "proxy"  # fcg-rewrite
    }

# User authentication function
async def require_authenticated_context(  # fcg-rewrite
    credentials: HTTPAuthorizationCredentials = Security(security),  # fcg-rewrite
    request: Request = None,  # fcg-rewrite
):
    """Verify user authentication (proxy service专用)"""
    # Use middleware to parse authentication context
    if request is not None:  # fcg-rewrite
        request_context = getattr(request.state, 'auth_context', None)  # fcg-rewrite
        if request_context:  # fcg-rewrite
            return request_context  # fcg-rewrite
    
    raise HTTPException(status_code=401, detail="Invalid API key")  # fcg-rewrite

# Register proxy routes - routes already contain /v1 prefix, no need to add again
app.include_router(openai_compat_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Register gateway integration API (for third-party AI gateways like Higress, LiteLLM, Kong)
# See docs/THIRD_PARTY_GATEWAY_INTEGRATION.md for full documentation
app.include_router(gateway_bridge_routes.router, dependencies=[Depends(require_authenticated_context)])  # fcg-rewrite

# Register direct model access API (uses its own authentication via model_api_key)
app.include_router(direct_model_routes.router, prefix="/v1")  # fcg-rewrite

# Global exception handling
@app.exception_handler(Exception)  # fcg-rewrite
async def handle_proxy_exception(request, exc):  # fcg-rewrite
    logger.error(f"Proxy service exception: {exc}")  # fcg-rewrite
    return JSONResponse(  # fcg-rewrite
        status_code=500,  # fcg-rewrite
        content={"error": {"message": "Proxy service internal error", "type": "internal_error"}}  # fcg-rewrite
    )

if __name__ == "__main__":  # fcg-rewrite
    uvicorn.run(  # fcg-rewrite
        "proxy_service:app",  # fcg-rewrite
        host=settings.host,  # fcg-rewrite
        port=settings.proxy_port,  # fcg-rewrite
        reload=settings.debug,  # fcg-rewrite
        log_level=settings.log_level.lower(),  # fcg-rewrite
        workers=settings.proxy_uvicorn_workers if not settings.debug else 1  # fcg-rewrite
    )
