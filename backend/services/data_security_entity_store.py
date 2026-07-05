"""Persistence helpers for sensitive-data entity types."""

from datetime import datetime  # fcg-rewrite
from typing import Any, Dict, List, Optional  # fcg-rewrite

from sqlalchemy import and_  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from database.models import DataSecurityEntityType, TenantEntityTypeDisable  # fcg-rewrite


class DataSecurityEntityStore:  # fcg-rewrite
    """Manage entity type configuration, template copies, and disable records."""

    def __init__(self, db: Session, logger):  # fcg-rewrite
        self.db = db  # fcg-rewrite
        self.logger = logger  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _entity_scope(tenant_id: str, application_id: Optional[str]):  # fcg-rewrite
        return (  # fcg-rewrite
            DataSecurityEntityType.application_id == application_id  # fcg-rewrite
            if application_id  # fcg-rewrite
            else DataSecurityEntityType.tenant_id == tenant_id  # fcg-rewrite
        )

    @staticmethod  # fcg-rewrite
    def _disable_filters(tenant_id: str, application_id: Optional[str] = None, entity_type: Optional[str] = None):  # fcg-rewrite
        filters = [TenantEntityTypeDisable.tenant_id == tenant_id]  # fcg-rewrite
        if application_id is not None:  # fcg-rewrite
            filters.append(TenantEntityTypeDisable.application_id == application_id)  # fcg-rewrite
        if entity_type is not None:  # fcg-rewrite
            filters.append(TenantEntityTypeDisable.entity_type == entity_type)  # fcg-rewrite
        return filters  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _detection_payload(entity) -> Dict[str, Any]:  # fcg-rewrite
        recognition = entity.recognition_config or {}  # fcg-rewrite
        return {  # fcg-rewrite
            "entity_type": entity.entity_type,  # fcg-rewrite
            "entity_type_name": entity.entity_type_name,  # fcg-rewrite
            "risk_level": entity.category,  # fcg-rewrite
            "recognition_method": entity.recognition_method,  # fcg-rewrite
            "pattern": recognition.get("pattern", ""),  # fcg-rewrite
            "entity_definition": recognition.get("entity_definition", ""),  # fcg-rewrite
            "anonymization_method": entity.anonymization_method,  # fcg-rewrite
            "anonymization_config": entity.anonymization_config or {},  # fcg-rewrite
            "restore_code": entity.restore_code,  # fcg-rewrite
            "restore_code_hash": entity.restore_code_hash,  # fcg-rewrite
        }

    def get_detection_entity_types(  # fcg-rewrite
        self, tenant_id: str, direction: str, application_id: Optional[str] = None  # fcg-rewrite
    ) -> List[Dict[str, Any]]:  # fcg-rewrite
        try:
            self._ensure_system_copies(tenant_id, application_id)  # fcg-rewrite
            disabled = {  # fcg-rewrite
                record.entity_type  # fcg-rewrite
                for record in self.db.query(TenantEntityTypeDisable)  # fcg-rewrite
                .filter(and_(*self._disable_filters(tenant_id, application_id)))  # fcg-rewrite
                .all()
            }
            entities = (  # fcg-rewrite
                self.db.query(DataSecurityEntityType)  # fcg-rewrite
                .filter(and_(DataSecurityEntityType.is_active == True, self._entity_scope(tenant_id, application_id)))  # fcg-rewrite
                .all()
            )
            self.logger.info("Found %s entity types for %s", len(entities), application_id or tenant_id)  # fcg-rewrite
            result = []  # fcg-rewrite
            for entity in entities:  # fcg-rewrite
                recognition = entity.recognition_config or {}  # fcg-rewrite
                if entity.entity_type in disabled:  # fcg-rewrite
                    continue  # fcg-rewrite
                if direction == "input" and not recognition.get("check_input", True):  # fcg-rewrite
                    continue  # fcg-rewrite
                if direction == "output" and not recognition.get("check_output", True):  # fcg-rewrite
                    continue  # fcg-rewrite
                result.append(self._detection_payload(entity))  # fcg-rewrite
            return result  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            self.logger.error("Error getting entity types: %s", error)  # fcg-rewrite
            return []  # fcg-rewrite

    def create_entity_type(  # fcg-rewrite
        self,
        tenant_id: str,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        entity_type: Optional[str] = None,  # fcg-rewrite
        entity_type_name: Optional[str] = None,  # fcg-rewrite
        risk_level: Optional[str] = None,  # fcg-rewrite
        pattern: Optional[str] = None,  # fcg-rewrite
        entity_definition: Optional[str] = None,  # fcg-rewrite
        recognition_method: str = "regex",  # fcg-rewrite
        anonymization_method: str = "replace",  # fcg-rewrite
        anonymization_config: Optional[Dict[str, Any]] = None,  # fcg-rewrite
        check_input: bool = True,  # fcg-rewrite
        check_output: bool = True,  # fcg-rewrite
        is_global: bool = False,  # fcg-rewrite
        source_type: str = "custom",  # fcg-rewrite
        template_id: Optional[str] = None,  # fcg-rewrite
        restore_natural_desc: Optional[str] = None,  # fcg-rewrite
    ) -> DataSecurityEntityType:  # fcg-rewrite
        recognition = {"check_input": check_input, "check_output": check_output}  # fcg-rewrite
        if recognition_method == "genai":  # fcg-rewrite
            recognition["entity_definition"] = entity_definition or entity_type_name  # fcg-rewrite
        else:
            recognition["pattern"] = pattern  # fcg-rewrite
        entity = DataSecurityEntityType(  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=None if is_global else application_id,  # fcg-rewrite
            entity_type=entity_type,  # fcg-rewrite
            entity_type_name=entity_type_name,  # fcg-rewrite
            category=risk_level,  # fcg-rewrite
            recognition_method=recognition_method,  # fcg-rewrite
            recognition_config=recognition,  # fcg-rewrite
            anonymization_method=anonymization_method,  # fcg-rewrite
            anonymization_config=anonymization_config or {},  # fcg-rewrite
            is_global=is_global,  # fcg-rewrite
            source_type="system_template" if is_global and source_type == "custom" else source_type,  # fcg-rewrite
            template_id=template_id,  # fcg-rewrite
            restore_natural_desc=restore_natural_desc,  # fcg-rewrite
        )
        self.db.add(entity)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        self.db.refresh(entity)  # fcg-rewrite
        return entity  # fcg-rewrite

    def update_entity_type(  # fcg-rewrite
        self, entity_type_id: str, tenant_id: str, application_id: Optional[str] = None, **kwargs  # fcg-rewrite
    ) -> Optional[DataSecurityEntityType]:  # fcg-rewrite
        scope = (  # fcg-rewrite
            (DataSecurityEntityType.application_id == application_id) | (DataSecurityEntityType.is_global == True)  # fcg-rewrite
            if application_id  # fcg-rewrite
            else DataSecurityEntityType.is_global == True  # fcg-rewrite
        )
        entity = self.db.query(DataSecurityEntityType).filter(and_(DataSecurityEntityType.id == entity_type_id, scope)).first()  # fcg-rewrite
        if not entity:  # fcg-rewrite
            return None  # fcg-rewrite
        for source, target in {  # fcg-rewrite
            "entity_type_name": "entity_type_name",  # fcg-rewrite
            "risk_level": "category",  # fcg-rewrite
            "recognition_method": "recognition_method",  # fcg-rewrite
            "is_active": "is_active",  # fcg-rewrite
            "restore_natural_desc": "restore_natural_desc",  # fcg-rewrite
            "restore_code": "restore_code",  # fcg-rewrite
            "restore_code_hash": "restore_code_hash",  # fcg-rewrite
        }.items():  # fcg-rewrite
            if source in kwargs:  # fcg-rewrite
                setattr(entity, target, kwargs[source])  # fcg-rewrite
        recognition = dict(entity.recognition_config or {})  # fcg-rewrite
        changed = False  # fcg-rewrite
        for field in ("pattern", "entity_definition", "check_input", "check_output"):  # fcg-rewrite
            if field in kwargs:  # fcg-rewrite
                recognition[field] = kwargs[field]  # fcg-rewrite
                changed = True  # fcg-rewrite
        if changed:  # fcg-rewrite
            entity.recognition_config = recognition  # fcg-rewrite
        if "anonymization_method" in kwargs:  # fcg-rewrite
            entity.anonymization_method = kwargs["anonymization_method"]  # fcg-rewrite
            if "anonymization_config" in kwargs:  # fcg-rewrite
                entity.anonymization_config = kwargs["anonymization_config"]  # fcg-rewrite
        entity.updated_at = datetime.utcnow()  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        self.db.refresh(entity)  # fcg-rewrite
        return entity  # fcg-rewrite

    def delete_entity_type(self, entity_type_id: str, tenant_id: str, application_id: Optional[str] = None) -> bool:  # fcg-rewrite
        entity = (  # fcg-rewrite
            self.db.query(DataSecurityEntityType)  # fcg-rewrite
            .filter(and_(DataSecurityEntityType.id == entity_type_id, self._entity_scope(tenant_id, application_id)))  # fcg-rewrite
            .first()  # fcg-rewrite
        )
        if not entity:  # fcg-rewrite
            return False  # fcg-rewrite
        self.db.delete(entity)  # fcg-rewrite
        self.db.commit()  # fcg-rewrite
        return True  # fcg-rewrite

    def get_entity_types(  # fcg-rewrite
        self,
        tenant_id: str,  # fcg-rewrite
        application_id: Optional[str] = None,  # fcg-rewrite
        risk_level: Optional[str] = None,  # fcg-rewrite
        is_active: Optional[bool] = None,  # fcg-rewrite
    ) -> List[DataSecurityEntityType]:  # fcg-rewrite
        if application_id:  # fcg-rewrite
            self._ensure_system_copies(tenant_id, application_id)  # fcg-rewrite
        query = self.db.query(DataSecurityEntityType).filter(self._entity_scope(tenant_id, application_id))  # fcg-rewrite
        if risk_level:  # fcg-rewrite
            query = query.filter(DataSecurityEntityType.category == risk_level)  # fcg-rewrite
        if is_active is not None:  # fcg-rewrite
            query = query.filter(DataSecurityEntityType.is_active == is_active)  # fcg-rewrite
        return query.order_by(DataSecurityEntityType.created_at.desc()).all()  # fcg-rewrite

    def _set_disabled(self, tenant_id: str, entity_type: str, disabled: bool, application_id: Optional[str] = None) -> bool:  # fcg-rewrite
        try:
            record = (  # fcg-rewrite
                self.db.query(TenantEntityTypeDisable)  # fcg-rewrite
                .filter(and_(*self._disable_filters(tenant_id, application_id, entity_type)))  # fcg-rewrite
                .first()  # fcg-rewrite
            )
            if disabled and not record:  # fcg-rewrite
                self.db.add(TenantEntityTypeDisable(tenant_id=tenant_id, application_id=application_id, entity_type=entity_type))  # fcg-rewrite
                self.db.commit()  # fcg-rewrite
            elif not disabled and record:  # fcg-rewrite
                self.db.delete(record)  # fcg-rewrite
                self.db.commit()  # fcg-rewrite
            return True  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            self.logger.error("Error setting disabled=%s for entity type %s: %s", disabled, entity_type, error)  # fcg-rewrite
            self.db.rollback()  # fcg-rewrite
            return False  # fcg-rewrite

    def _get_disabled(self, tenant_id: str, application_id: Optional[str] = None) -> List[str]:  # fcg-rewrite
        try:
            records = self.db.query(TenantEntityTypeDisable).filter(and_(*self._disable_filters(tenant_id, application_id))).all()  # fcg-rewrite
            return [record.entity_type for record in records]  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            self.logger.error("Error getting disabled entity types: %s", error)  # fcg-rewrite
            return []  # fcg-rewrite

    def disable_entity_type_for_application(self, tenant_id: str, application_id: str, entity_type: str) -> bool:  # fcg-rewrite
        return self._set_disabled(tenant_id, entity_type, True, application_id)  # fcg-rewrite

    def enable_entity_type_for_application(self, tenant_id: str, application_id: str, entity_type: str) -> bool:  # fcg-rewrite
        return self._set_disabled(tenant_id, entity_type, False, application_id)  # fcg-rewrite

    def get_application_disabled_entity_types(self, tenant_id: str, application_id: str) -> List[str]:  # fcg-rewrite
        return self._get_disabled(tenant_id, application_id)  # fcg-rewrite

    def disable_entity_type_for_tenant(self, tenant_id: str, entity_type: str) -> bool:  # fcg-rewrite
        return self._set_disabled(tenant_id, entity_type, True)  # fcg-rewrite

    def enable_entity_type_for_tenant(self, tenant_id: str, entity_type: str) -> bool:  # fcg-rewrite
        return self._set_disabled(tenant_id, entity_type, False)  # fcg-rewrite

    def get_tenant_disabled_entity_types(self, tenant_id: str) -> List[str]:  # fcg-rewrite
        return self._get_disabled(tenant_id)  # fcg-rewrite

    def _ensure_system_copies(self, tenant_id: str, application_id: Optional[str]) -> int:  # fcg-rewrite
        try:
            templates = (  # fcg-rewrite
                self.db.query(DataSecurityEntityType)  # fcg-rewrite
                .filter(DataSecurityEntityType.source_type == "system_template")  # fcg-rewrite
                .all()
            )
            if not templates:  # fcg-rewrite
                return 0  # fcg-rewrite
            existing = self.db.query(DataSecurityEntityType).filter(self._entity_scope(tenant_id, application_id)).all()  # fcg-rewrite
            template_ids = {str(entity.template_id) for entity in existing if entity.template_id}  # fcg-rewrite
            created = 0  # fcg-rewrite
            for template in templates:  # fcg-rewrite
                if str(template.id) in template_ids:  # fcg-rewrite
                    continue  # fcg-rewrite
                self.db.add(self._build_system_copy(template, tenant_id, application_id))  # fcg-rewrite
                created += 1  # fcg-rewrite
            if created:  # fcg-rewrite
                self.db.commit()  # fcg-rewrite
                self.logger.info("Created %s system entity type copies for %s", created, application_id or tenant_id)  # fcg-rewrite
            return created  # fcg-rewrite
        except Exception as error:  # fcg-rewrite
            self.logger.error("Error ensuring system entity type copies for %s: %s", application_id or tenant_id, error)  # fcg-rewrite
            self.db.rollback()  # fcg-rewrite
            return 0  # fcg-rewrite

    def ensure_application_has_system_copies(self, tenant_id: str, application_id: str) -> int:  # fcg-rewrite
        return self._ensure_system_copies(tenant_id, application_id)  # fcg-rewrite

    def ensure_tenant_has_system_copies(self, tenant_id: str) -> int:  # fcg-rewrite
        return self._ensure_system_copies(tenant_id, None)  # fcg-rewrite

    @staticmethod  # fcg-rewrite
    def _build_system_copy(template: DataSecurityEntityType, tenant_id: str, application_id: Optional[str]):  # fcg-rewrite
        return DataSecurityEntityType(  # fcg-rewrite
            tenant_id=tenant_id,  # fcg-rewrite
            application_id=application_id,  # fcg-rewrite
            entity_type=template.entity_type,  # fcg-rewrite
            entity_type_name=template.entity_type_name,  # fcg-rewrite
            category=template.category,  # fcg-rewrite
            recognition_method=template.recognition_method,  # fcg-rewrite
            recognition_config=dict(template.recognition_config or {}),  # fcg-rewrite
            anonymization_method=template.anonymization_method,  # fcg-rewrite
            anonymization_config=dict(template.anonymization_config or {}),  # fcg-rewrite
            is_active=template.is_active,  # fcg-rewrite
            is_global=False,  # fcg-rewrite
            source_type="system_copy",  # fcg-rewrite
            template_id=template.id,  # fcg-rewrite
        )
