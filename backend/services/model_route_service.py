"""Tenant model routing rules for upstream selection."""

import uuid  # fcg-rewrite
from typing import List, Optional  # fcg-rewrite

from sqlalchemy import desc  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import ModelRoute, ModelRouteApplication, UpstreamApiConfig  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite


class ModelRouteRegistry:  # fcg-rewrite
    @staticmethod  # fcg-rewrite
    def find_matching_route(  # fcg-rewrite
        db: Session,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        model_name: str,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
    ) -> Optional[UpstreamApiConfig]:  # fcg-rewrite
        try:
            tenant_uuid = uuid.UUID(tenant_id)  # fcg-rewrite
            application_uuid = uuid.UUID(application_id) if application_id else None  # fcg-rewrite
            routes = db.query(ModelRoute).filter(  # fcg-rewrite
                ModelRoute.tenant_id == tenant_uuid,  # fcg-rewrite
                ModelRoute.is_active == True,  # fcg-rewrite
            ).all()
            scoped, global_routes = [], []  # fcg-rewrite
            for route in routes:  # fcg-rewrite
                bindings = route.route_applications  # fcg-rewrite
                if not bindings:  # fcg-rewrite
                    global_routes.append(route)  # fcg-rewrite
                elif application_uuid and any(  # fcg-rewrite
                    binding.application_id == application_uuid for binding in bindings  # fcg-rewrite
                ):
                    scoped.append(route)  # fcg-rewrite
            match = ModelRouteRegistry._best_match(scoped, model_name)  # fcg-rewrite
            match = match or ModelRouteRegistry._best_match(global_routes, model_name)  # fcg-rewrite
            return match.upstream_api_config if match else None  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to match model route: {exc}", exc_info=True)  # fcg-rewrite
            return None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def get_routes_for_tenant(  # fcg-rewrite
        db: Session, tenant_id: str, include_inactive: bool = False  # fcg-rewrite
    ) -> List[ModelRoute]:  # fcg-rewrite
        try:
            query = db.query(ModelRoute).filter(  # fcg-rewrite
                ModelRoute.tenant_id == uuid.UUID(tenant_id)  # fcg-rewrite
            )
            if not include_inactive:  # fcg-rewrite
                query = query.filter(ModelRoute.is_active == True)  # fcg-rewrite
            return query.order_by(desc(ModelRoute.priority)).all()  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to list model routes: {exc}", exc_info=True)  # fcg-rewrite
            return []  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def create_route(  # fcg-rewrite
        db: Session,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        name: str,  # fcg-rewrite
        model_pattern: str,  # fcg-rewrite
        upstream_api_config_id: str,  # fcg-rewrite
        match_type: str = "prefix",  # fcg-rewrite
        priority: int = 100,  # fcg-rewrite
        description: Optional[str] = None,  # fcg-rewrite
        application_ids: Optional[List[str]] = None,  # fcg-rewrite
    ) -> Optional[ModelRoute]:  # fcg-rewrite
        try:
            route = ModelRoute(  # fcg-rewrite
                tenant_id=uuid.UUID(tenant_id),  # fcg-rewrite
                name=name,  # fcg-rewrite
                model_pattern=model_pattern,  # fcg-rewrite
                match_type=match_type,  # fcg-rewrite
                upstream_api_config_id=uuid.UUID(upstream_api_config_id),  # fcg-rewrite
                priority=priority,  # fcg-rewrite
                description=description,  # fcg-rewrite
                is_active=True,  # fcg-rewrite
            )
            db.add(route)  # fcg-rewrite
            db.flush()  # fcg-rewrite
            ModelRouteRegistry._add_bindings(db, route.id, application_ids or [])  # fcg-rewrite
            return ModelRouteRegistry._commit(db, route)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            logger.error(f"Failed to create model route: {exc}", exc_info=True)  # fcg-rewrite
            return None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def update_route(  # fcg-rewrite
        db: Session,  # fcg-rewrite
        route_id: str,  # fcg-rewrite
        tenant_id: str,  # fcg-rewrite
        updates: dict,  # fcg-rewrite
        application_ids: Optional[List[str]] = None,  # fcg-rewrite
    ) -> Optional[ModelRoute]:  # fcg-rewrite
        try:
            route_uuid = uuid.UUID(route_id)  # fcg-rewrite
            route = ModelRouteRegistry._owned_route(db, route_uuid, tenant_id)  # fcg-rewrite
            if not route:  # fcg-rewrite
                return None  # fcg-rewrite
            for key, value in updates.items():  # fcg-rewrite
                if hasattr(route, key) and key not in {"id", "tenant_id", "created_at"}:  # fcg-rewrite
                    setattr(route, key, value)  # fcg-rewrite
            if application_ids is not None:  # fcg-rewrite
                db.query(ModelRouteApplication).filter(  # fcg-rewrite
                    ModelRouteApplication.model_route_id == route_uuid  # fcg-rewrite
                ).delete()  # fcg-rewrite
                ModelRouteRegistry._add_bindings(db, route.id, application_ids)  # fcg-rewrite
            return ModelRouteRegistry._commit(db, route)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            logger.error(f"Failed to update model route: {exc}", exc_info=True)  # fcg-rewrite
            return None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def delete_route(db: Session, route_id: str, tenant_id: str) -> bool:  # fcg-rewrite
        try:
            route = ModelRouteRegistry._owned_route(db, uuid.UUID(route_id), tenant_id)  # fcg-rewrite
            if not route:  # fcg-rewrite
                return False  # fcg-rewrite
            db.delete(route)  # fcg-rewrite
            db.commit()  # fcg-rewrite
            return True  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
            logger.error(f"Failed to delete model route: {exc}", exc_info=True)  # fcg-rewrite
            return False  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def get_route_by_id(  # fcg-rewrite
        db: Session, route_id: str, tenant_id: str  # fcg-rewrite
    ) -> Optional[ModelRoute]:  # fcg-rewrite
        try:
            return ModelRouteRegistry._owned_route(db, uuid.UUID(route_id), tenant_id)  # fcg-rewrite
        except Exception as exc:  # fcg-rewrite
            logger.error(f"Failed to load model route: {exc}", exc_info=True)  # fcg-rewrite
            return None  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _best_match(routes: List[ModelRoute], model_name: str) -> Optional[ModelRoute]:  # fcg-rewrite
        model_name = model_name.lower()  # fcg-rewrite

        def matches(route):  # fcg-rewrite
            pattern = route.model_pattern.lower()  # fcg-rewrite
            return model_name == pattern if route.match_type == "exact" else model_name.startswith(pattern)  # fcg-rewrite

        candidates = [route for route in routes if matches(route)]  # fcg-rewrite
        return max(  # fcg-rewrite
            candidates,  # fcg-rewrite
            key=lambda route: (route.priority, route.match_type == "exact"),  # fcg-rewrite
            default=None,  # fcg-rewrite
        )

    @staticmethod  # fcg-rewrite
    def _owned_route(db: Session, route_id: uuid.UUID, tenant_id: str):  # fcg-rewrite
        return db.query(ModelRoute).filter(  # fcg-rewrite
            ModelRoute.id == route_id,  # fcg-rewrite
            ModelRoute.tenant_id == uuid.UUID(tenant_id),  # fcg-rewrite
        ).first()  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _add_bindings(db: Session, route_id, application_ids: List[str]):  # fcg-rewrite
        for application_id in application_ids:  # fcg-rewrite
            db.add(
                ModelRouteApplication(  # fcg-rewrite
                    model_route_id=route_id,  # fcg-rewrite
                    application_id=uuid.UUID(application_id),  # fcg-rewrite
                )
            )

    @staticmethod  # fcg-rewrite
    def _commit(db: Session, route: ModelRoute) -> ModelRoute:  # fcg-rewrite
        db.commit()  # fcg-rewrite
        db.refresh(route)  # fcg-rewrite
        return route  # fcg-rewrite


model_route_service = ModelRouteRegistry()  # fcg-rewrite
