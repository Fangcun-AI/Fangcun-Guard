"""CRUD endpoints for tenant-owned upstream model routing rules."""

from typing import Annotated, List, Optional  # fcg-rewrite
import uuid  # fcg-rewrite

from fastapi import APIRouter, Depends, HTTPException, Request  # fcg-rewrite
from pydantic import BaseModel, Field  # fcg-rewrite

from database.connection import get_db  # fcg-rewrite
from database.models import Application, ModelRoute, UpstreamApiConfig  # fcg-rewrite
from services.model_route_service import model_route_service  # fcg-rewrite

router = APIRouter(prefix="/api/v1/model-routes", tags=["Model Routes"])  # fcg-rewrite
MatchType = Annotated[str, Field(pattern="^(exact|prefix)$")]  # fcg-rewrite


class ModelRouteCreateRequest(BaseModel):  # fcg-rewrite
    name: str = Field(min_length=1, max_length=200)  # fcg-rewrite
    description: Optional[str] = None  # fcg-rewrite
    model_pattern: str = Field(min_length=1, max_length=255)  # fcg-rewrite
    match_type: MatchType = "prefix"  # fcg-rewrite
    upstream_api_config_id: str  # fcg-rewrite
    priority: int = Field(default=100, ge=0, le=10000)  # fcg-rewrite
    application_ids: Optional[List[str]] = None  # fcg-rewrite


class ModelRouteUpdateRequest(BaseModel):  # fcg-rewrite
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)  # fcg-rewrite
    description: Optional[str] = None  # fcg-rewrite
    model_pattern: Optional[str] = Field(default=None, min_length=1, max_length=255)  # fcg-rewrite
    match_type: Optional[MatchType] = None  # fcg-rewrite
    upstream_api_config_id: Optional[str] = None  # fcg-rewrite
    priority: Optional[int] = Field(default=None, ge=0, le=10000)  # fcg-rewrite
    is_active: Optional[bool] = None  # fcg-rewrite
    application_ids: Optional[List[str]] = None  # fcg-rewrite


class ApplicationInfo(BaseModel):  # fcg-rewrite
    id: str
    name: str  # fcg-rewrite


class UpstreamApiInfo(BaseModel):  # fcg-rewrite
    id: str
    config_name: str  # fcg-rewrite
    provider: Optional[str]  # fcg-rewrite


class ModelRouteResponse(BaseModel):  # fcg-rewrite
    id: str
    name: str  # fcg-rewrite
    description: Optional[str]  # fcg-rewrite
    model_pattern: str  # fcg-rewrite
    match_type: str  # fcg-rewrite
    upstream_api_config: UpstreamApiInfo  # fcg-rewrite
    priority: int  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    applications: List[ApplicationInfo]  # fcg-rewrite
    created_at: str  # fcg-rewrite
    updated_at: str  # fcg-rewrite


def get_tenant_id_from_request(request: Request) -> str:  # fcg-rewrite
    context = getattr(request.state, "auth_context", None)  # fcg-rewrite
    tenant_id = context.get("data", {}).get("tenant_id") if isinstance(context, dict) else None  # fcg-rewrite
    if not tenant_id:  # fcg-rewrite
        raise HTTPException(status_code=401, detail="Authentication required")  # fcg-rewrite
    return str(tenant_id)  # fcg-rewrite


def route_to_response(route: ModelRoute) -> ModelRouteResponse:  # fcg-rewrite
    upstream = route.upstream_api_config  # fcg-rewrite
    return ModelRouteResponse(  # fcg-rewrite
        id=str(route.id),  # fcg-rewrite
        name=route.name,  # fcg-rewrite
        description=route.description,  # fcg-rewrite
        model_pattern=route.model_pattern,  # fcg-rewrite
        match_type=route.match_type,  # fcg-rewrite
        upstream_api_config=UpstreamApiInfo(id=str(upstream.id), config_name=upstream.config_name, provider=upstream.provider),  # fcg-rewrite
        priority=route.priority,  # fcg-rewrite
        is_active=route.is_active,  # fcg-rewrite
        applications=[  # fcg-rewrite
            ApplicationInfo(id=str(binding.application.id), name=binding.application.name)  # fcg-rewrite
            for binding in route.route_applications  # fcg-rewrite
        ],
        created_at=route.created_at.isoformat() if route.created_at else "",  # fcg-rewrite
        updated_at=route.updated_at.isoformat() if route.updated_at else "",  # fcg-rewrite
    )


def _uuid(value: str, detail: str) -> uuid.UUID:  # fcg-rewrite
    try:
        return uuid.UUID(value)  # fcg-rewrite
    except ValueError as exc:  # fcg-rewrite
        raise HTTPException(status_code=400, detail=detail) from exc  # fcg-rewrite


def _validate_references(db, tenant_id: str, upstream_id: Optional[str], application_ids):  # fcg-rewrite
    tenant_uuid = _uuid(tenant_id, "Invalid tenant ID format")  # fcg-rewrite
    if upstream_id:  # fcg-rewrite
        upstream_uuid = _uuid(upstream_id, "Invalid upstream_api_config_id format")  # fcg-rewrite
        if not db.query(UpstreamApiConfig).filter(  # fcg-rewrite
            UpstreamApiConfig.id == upstream_uuid, UpstreamApiConfig.tenant_id == tenant_uuid  # fcg-rewrite
        ).first():  # fcg-rewrite
            raise HTTPException(status_code=400, detail="Invalid upstream_api_config_id")  # fcg-rewrite
    if application_ids is not None:  # fcg-rewrite
        for application_id in application_ids:  # fcg-rewrite
            app_uuid = _uuid(application_id, f"Invalid application_id format: {application_id}")  # fcg-rewrite
            if not db.query(Application).filter(  # fcg-rewrite
                Application.id == app_uuid, Application.tenant_id == tenant_uuid  # fcg-rewrite
            ).first():  # fcg-rewrite
                raise HTTPException(status_code=400, detail=f"Invalid application_id: {application_id}")  # fcg-rewrite


@router.get("", response_model=List[ModelRouteResponse])  # fcg-rewrite
async def list_model_routes(request: Request, include_inactive: bool = False, db=Depends(get_db)):  # fcg-rewrite
    routes = model_route_service.get_routes_for_tenant(  # fcg-rewrite
        db=db, tenant_id=get_tenant_id_from_request(request), include_inactive=include_inactive  # fcg-rewrite
    )
    return [route_to_response(route) for route in routes]  # fcg-rewrite


@router.get("/{route_id}", response_model=ModelRouteResponse)  # fcg-rewrite
async def get_model_route(route_id: str, request: Request, db=Depends(get_db)):  # fcg-rewrite
    route = model_route_service.get_route_by_id(  # fcg-rewrite
        db=db, route_id=route_id, tenant_id=get_tenant_id_from_request(request)  # fcg-rewrite
    )
    if not route:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Route not found")  # fcg-rewrite
    return route_to_response(route)  # fcg-rewrite


@router.post("", response_model=ModelRouteResponse, status_code=201)  # fcg-rewrite
async def create_model_route(route_data: ModelRouteCreateRequest, request: Request, db=Depends(get_db)):  # fcg-rewrite
    tenant_id = get_tenant_id_from_request(request)  # fcg-rewrite
    _validate_references(db, tenant_id, route_data.upstream_api_config_id, route_data.application_ids)  # fcg-rewrite
    route = model_route_service.create_route(db=db, tenant_id=tenant_id, **route_data.model_dump())  # fcg-rewrite
    if not route:  # fcg-rewrite
        raise HTTPException(status_code=500, detail="Failed to create route")  # fcg-rewrite
    db.refresh(route)  # fcg-rewrite
    return route_to_response(route)  # fcg-rewrite


@router.put("/{route_id}", response_model=ModelRouteResponse)  # fcg-rewrite
async def update_model_route(  # fcg-rewrite
    route_id: str, route_data: ModelRouteUpdateRequest, request: Request, db=Depends(get_db)  # fcg-rewrite
):
    tenant_id = get_tenant_id_from_request(request)  # fcg-rewrite
    _validate_references(db, tenant_id, route_data.upstream_api_config_id, route_data.application_ids)  # fcg-rewrite
    values = route_data.model_dump(exclude={"application_ids"}, exclude_none=True)  # fcg-rewrite
    route = model_route_service.update_route(  # fcg-rewrite
        db=db, route_id=route_id, tenant_id=tenant_id, updates=values, application_ids=route_data.application_ids  # fcg-rewrite
    )
    if not route:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Route not found")  # fcg-rewrite
    db.refresh(route)  # fcg-rewrite
    return route_to_response(route)  # fcg-rewrite


@router.delete("/{route_id}")  # fcg-rewrite
async def delete_model_route(route_id: str, request: Request, db=Depends(get_db)):  # fcg-rewrite
    if not model_route_service.delete_route(  # fcg-rewrite
        db=db, route_id=route_id, tenant_id=get_tenant_id_from_request(request)  # fcg-rewrite
    ):
        raise HTTPException(status_code=404, detail="Route not found")  # fcg-rewrite
    return {"success": True, "message": "Route deleted successfully"}  # fcg-rewrite


@router.get("/test/{model_name}")  # fcg-rewrite
async def test_model_routing(  # fcg-rewrite
    model_name: str, request: Request, application_id: Optional[str] = None, db=Depends(get_db)  # fcg-rewrite
):
    upstream = model_route_service.find_matching_route(  # fcg-rewrite
        db=db,
        tenant_id=get_tenant_id_from_request(request),  # fcg-rewrite
        model_name=model_name,  # fcg-rewrite
        application_id=application_id,  # fcg-rewrite
    )
    if not upstream:  # fcg-rewrite
        return {"matched": False, "model_name": model_name, "message": "No matching route found. Please configure a routing rule for this model."}  # fcg-rewrite
    return {  # fcg-rewrite
        "matched": True,  # fcg-rewrite
        "model_name": model_name,  # fcg-rewrite
        "upstream_api_config": {  # fcg-rewrite
            "id": str(upstream.id),  # fcg-rewrite
            "config_name": upstream.config_name,  # fcg-rewrite
            "provider": upstream.provider,  # fcg-rewrite
            "api_base_url": upstream.api_base_url,  # fcg-rewrite
        },
    }
