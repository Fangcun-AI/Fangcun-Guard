"""Data-security entity type administration endpoints."""

import hashlib  # fcg-rewrite
from inspect import isawaitable  # fcg-rewrite
from time import time  # fcg-rewrite
from typing import Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from fastapi import APIRouter, Depends, HTTPException, Request  # fcg-rewrite
from sqlalchemy import and_  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from database.models import DataSecurityEntityType  # fcg-rewrite
from services.application_request_context import resolve_admin_application_context  # fcg-rewrite
from services.data_security_service import PrivacyEngine  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite
from utils.subscription_check import SubscriptionFeature, get_feature_availability, require_subscription_for_feature  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Data Security"])  # fcg-rewrite


def get_current_user_and_application_from_request(request: Request, db: Session):  # fcg-rewrite
    context = resolve_admin_application_context(request, db)  # fcg-rewrite
    return context.tenant, context.application_id  # fcg-rewrite


async def _invoke(label: str, failure: str, operation, *, invalid=()):  # fcg-rewrite
    try:
        result = operation()  # fcg-rewrite
        return await result if isawaitable(result) else result  # fcg-rewrite
    except invalid as error:  # fcg-rewrite
        logger.error("%s error: %s", label, error)  # fcg-rewrite
        raise HTTPException(status_code=400, detail=str(error))  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as error:  # fcg-rewrite
        logger.error("%s error: %s", label, error, exc_info=True)  # fcg-rewrite
        raise HTTPException(status_code=500, detail=f"{failure}: {error}")  # fcg-rewrite


def _scope(request: Request, db: Session):  # fcg-rewrite
    tenant, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
    return tenant, application_id, PrivacyEngine(db)  # fcg-rewrite


def _required(data: dict, field: str, label: str):  # fcg-rewrite
    value = data.get(field, "")  # fcg-rewrite
    if not value:  # fcg-rewrite
        raise HTTPException(status_code=400, detail=f"{label} is required")  # fcg-rewrite
    return value  # fcg-rewrite


def _premium(tenant, db: Session, *features: SubscriptionFeature) -> None:  # fcg-rewrite
    for feature in features:  # fcg-rewrite
        require_subscription_for_feature(  # fcg-rewrite
            tenant_id=str(tenant.id),  # fcg-rewrite
            db=db,
            feature=feature,  # fcg-rewrite
            language=settings.default_language,  # fcg-rewrite
        )


def _recognition_method(data: dict, default=None):  # fcg-rewrite
    method = data.get("recognition_method", default)  # fcg-rewrite
    if data.get("entity_definition") and not data.get("pattern"):  # fcg-rewrite
        logger.info("Auto-corrected recognition_method to 'genai' based on entity_definition presence")  # fcg-rewrite
        return "genai"  # fcg-rewrite
    return method  # fcg-rewrite


def _entity_payload(entity, *, include_code: bool = False) -> dict:  # fcg-rewrite
    recognition = entity.recognition_config or {}  # fcg-rewrite
    payload = {  # fcg-rewrite
        "id": str(entity.id),  # fcg-rewrite
        "entity_type": entity.entity_type,  # fcg-rewrite
        "entity_type_name": entity.entity_type_name,  # fcg-rewrite
        "category": entity.category,  # fcg-rewrite
        "recognition_method": entity.recognition_method,  # fcg-rewrite
        "pattern": recognition.get("pattern", ""),  # fcg-rewrite
        "entity_definition": recognition.get("entity_definition", ""),  # fcg-rewrite
        "anonymization_method": entity.anonymization_method,  # fcg-rewrite
        "anonymization_config": entity.anonymization_config,  # fcg-rewrite
        "check_input": recognition.get("check_input", True),  # fcg-rewrite
        "check_output": recognition.get("check_output", True),  # fcg-rewrite
        "is_active": entity.is_active,  # fcg-rewrite
        "source_type": entity.source_type,  # fcg-rewrite
        "is_system_template": entity.source_type == "system_template",  # fcg-rewrite
        "created_at": entity.created_at.isoformat() if entity.created_at else None,  # fcg-rewrite
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,  # fcg-rewrite
    }
    if include_code:  # fcg-rewrite
        payload.update(  # fcg-rewrite
            genai_code_desc=entity.restore_natural_desc,  # fcg-rewrite
            genai_code=entity.restore_code,  # fcg-rewrite
            has_genai_code=bool(entity.restore_code),  # fcg-rewrite
        )
    return payload  # fcg-rewrite


def _owned_entity(db: Session, entity_type_id: str, tenant):  # fcg-rewrite
    entity = db.query(DataSecurityEntityType).filter(DataSecurityEntityType.id == entity_type_id).first()  # fcg-rewrite
    if not entity:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Entity type not found")  # fcg-rewrite
    if str(entity.tenant_id) != str(tenant.id) and not tenant.is_super_admin:  # fcg-rewrite
        raise HTTPException(status_code=403, detail="Access denied")  # fcg-rewrite
    return entity  # fcg-rewrite


def _restore_service():  # fcg-rewrite
    from services.restore_anonymization_service import get_restore_anonymization_service  # fcg-rewrite

    return get_restore_anonymization_service()  # fcg-rewrite


@router.get("/config/data-security/entity-types")  # fcg-rewrite
async def get_entity_types(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    risk_level: Optional[str] = None,  # fcg-rewrite
    is_active: Optional[bool] = None,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    tenant, application_id, engine = _scope(request, db)  # fcg-rewrite
    entities = await _invoke(  # fcg-rewrite
        "Get entity types",  # fcg-rewrite
        "Failed to get entity types",  # fcg-rewrite
        lambda: engine.get_entity_types(  # fcg-rewrite
            tenant_id=str(tenant.id),  # fcg-rewrite
            application_id=str(application_id),  # fcg-rewrite
            risk_level=risk_level,  # fcg-rewrite
            is_active=is_active,  # fcg-rewrite
        ),
    )
    items = [_entity_payload(entity, include_code=True) for entity in entities]  # fcg-rewrite
    return {"items": items, "total": len(items)}  # fcg-rewrite


@router.get("/config/data-security/entity-types/{entity_type_id}")  # fcg-rewrite
async def get_entity_type(entity_type_id: str, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    _, application_id, _ = _scope(request, db)  # fcg-rewrite
    try:
        entity_uuid = UUID(entity_type_id)  # fcg-rewrite
    except (TypeError, ValueError):  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Invalid entity type ID format")  # fcg-rewrite
    entity = await _invoke(  # fcg-rewrite
        "Get entity type",  # fcg-rewrite
        "Failed to get entity type",  # fcg-rewrite
        lambda: db.query(DataSecurityEntityType)  # fcg-rewrite
        .filter(  # fcg-rewrite
            and_(
                DataSecurityEntityType.id == entity_uuid,  # fcg-rewrite
                (DataSecurityEntityType.application_id == application_id)  # fcg-rewrite
                | (DataSecurityEntityType.source_type == "system_template"),  # fcg-rewrite
            )
        )
        .first(),  # fcg-rewrite
    )
    if not entity:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Entity type not found")  # fcg-rewrite
    return _entity_payload(entity)  # fcg-rewrite


def _create_entity(engine: PrivacyEngine, tenant, application_id, data: dict, *, global_entity: bool):  # fcg-rewrite
    recognition_method = _recognition_method(data, "regex")  # fcg-rewrite
    anonymization_method = data.get("anonymization_method", "mask")  # fcg-rewrite
    entity = engine.create_entity_type(  # fcg-rewrite
        tenant_id=str(tenant.id),  # fcg-rewrite
        application_id=None if global_entity else str(application_id),  # fcg-rewrite
        entity_type=data.get("entity_type"),  # fcg-rewrite
        entity_type_name=data.get("entity_type_name"),  # fcg-rewrite
        risk_level=data.get("category", "medium"),  # fcg-rewrite
        recognition_method=recognition_method,  # fcg-rewrite
        pattern=data.get("pattern"),  # fcg-rewrite
        entity_definition=data.get("entity_definition"),  # fcg-rewrite
        anonymization_method=anonymization_method,  # fcg-rewrite
        anonymization_config=data.get("anonymization_config"),  # fcg-rewrite
        check_input=data.get("check_input", True),  # fcg-rewrite
        check_output=data.get("check_output", True),  # fcg-rewrite
        is_global=global_entity,  # fcg-rewrite
        source_type="system_template" if global_entity else "custom",  # fcg-rewrite
        **({} if global_entity else {"restore_natural_desc": data.get("genai_code_desc") or data.get("restore_natural_desc")}),  # fcg-rewrite
    )
    return entity, anonymization_method  # fcg-rewrite


@router.post("/config/data-security/entity-types")  # fcg-rewrite
async def create_entity_type(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, application_id, engine = _scope(request, db)  # fcg-rewrite
    recognition_method = _recognition_method(data, "regex")  # fcg-rewrite
    anonymization_method = data.get("anonymization_method", "mask")  # fcg-rewrite
    if recognition_method == "genai":  # fcg-rewrite
        _premium(tenant, db, SubscriptionFeature.GENAI_RECOGNITION)  # fcg-rewrite
    if anonymization_method == "genai_code":  # fcg-rewrite
        _premium(tenant, db, SubscriptionFeature.GENAI_CODE_ANONYMIZATION)  # fcg-rewrite
    if data.get("genai_code_desc") or data.get("restore_natural_desc"):  # fcg-rewrite
        _premium(tenant, db, SubscriptionFeature.NATURAL_LANGUAGE_DESC)  # fcg-rewrite

    entity, _ = await _invoke(  # fcg-rewrite
        "Create entity type",  # fcg-rewrite
        "Failed to create entity type",  # fcg-rewrite
        lambda: _create_entity(engine, tenant, application_id, data, global_entity=False),  # fcg-rewrite
    )
    code = data.get("genai_code")  # fcg-rewrite
    if code and anonymization_method == "genai_code":  # fcg-rewrite
        entity.restore_code = code  # fcg-rewrite
        entity.restore_code_hash = hashlib.sha256(code.encode()).hexdigest()  # fcg-rewrite
        db.commit()  # fcg-rewrite
    logger.info("Entity type created: %s for user %s, app %s", data.get("entity_type"), tenant.email, application_id)  # fcg-rewrite
    return {"success": True, "message": "Entity type created successfully", "id": str(entity.id)}  # fcg-rewrite


def _entity_updates(data: dict, tenant, db: Session) -> dict:  # fcg-rewrite
    updates = {}  # fcg-rewrite
    aliases = {  # fcg-rewrite
        "entity_type_name": "entity_type_name",  # fcg-rewrite
        "category": "risk_level",  # fcg-rewrite
        "pattern": "pattern",  # fcg-rewrite
        "entity_definition": "entity_definition",  # fcg-rewrite
        "anonymization_method": "anonymization_method",  # fcg-rewrite
        "anonymization_config": "anonymization_config",  # fcg-rewrite
        "check_input": "check_input",  # fcg-rewrite
        "check_output": "check_output",  # fcg-rewrite
        "is_active": "is_active",  # fcg-rewrite
    }
    recognition_method = _recognition_method(data)  # fcg-rewrite
    if recognition_method == "genai":  # fcg-rewrite
        _premium(tenant, db, SubscriptionFeature.GENAI_RECOGNITION)  # fcg-rewrite
    if recognition_method is not None:  # fcg-rewrite
        updates["recognition_method"] = recognition_method  # fcg-rewrite
    for source, target in aliases.items():  # fcg-rewrite
        if source in data:  # fcg-rewrite
            updates[target] = data[source]  # fcg-rewrite
    if data.get("anonymization_method") == "genai_code":  # fcg-rewrite
        _premium(tenant, db, SubscriptionFeature.GENAI_CODE_ANONYMIZATION)  # fcg-rewrite
    for field in ("genai_code_desc", "restore_natural_desc"):  # fcg-rewrite
        if field in data:  # fcg-rewrite
            _premium(tenant, db, SubscriptionFeature.NATURAL_LANGUAGE_DESC)  # fcg-rewrite
            updates["restore_natural_desc"] = data[field]  # fcg-rewrite
            break
    code = data.get("genai_code")  # fcg-rewrite
    if code and data.get("anonymization_method") == "genai_code":  # fcg-rewrite
        updates["restore_code"] = code  # fcg-rewrite
        updates["restore_code_hash"] = hashlib.sha256(code.encode()).hexdigest()  # fcg-rewrite
    return updates  # fcg-rewrite


@router.put("/config/data-security/entity-types/{entity_type_id}")  # fcg-rewrite
async def update_entity_type(entity_type_id: str, data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, application_id, engine = _scope(request, db)  # fcg-rewrite
    result = await _invoke(  # fcg-rewrite
        "Update entity type",  # fcg-rewrite
        "Failed to update entity type",  # fcg-rewrite
        lambda: engine.update_entity_type(  # fcg-rewrite
            entity_type_id=entity_type_id,  # fcg-rewrite
            tenant_id=str(tenant.id),  # fcg-rewrite
            application_id=str(application_id),  # fcg-rewrite
            **_entity_updates(data, tenant, db),  # fcg-rewrite
        ),
    )
    if not result:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Entity type not found or update failed")  # fcg-rewrite
    logger.info("Entity type updated: %s for user %s, app %s", entity_type_id, tenant.email, application_id)  # fcg-rewrite
    return {"success": True, "message": "Entity type updated successfully"}  # fcg-rewrite


@router.delete("/config/data-security/entity-types/{entity_type_id}")  # fcg-rewrite
async def delete_entity_type(entity_type_id: str, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, application_id, engine = _scope(request, db)  # fcg-rewrite
    conditions = [DataSecurityEntityType.id == entity_type_id]  # fcg-rewrite
    conditions.append(  # fcg-rewrite
        DataSecurityEntityType.application_id == application_id if application_id else DataSecurityEntityType.tenant_id == tenant.id  # fcg-rewrite
    )
    entity = db.query(DataSecurityEntityType).filter(and_(*conditions)).first()  # fcg-rewrite
    if not entity:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Entity type not found")  # fcg-rewrite
    source_type = entity.source_type or ("system_template" if entity.is_global else "custom")  # fcg-rewrite
    if source_type == "system_template" and not tenant.is_super_admin:  # fcg-rewrite
        raise HTTPException(status_code=403, detail="Only super administrators can delete system entity type templates")  # fcg-rewrite
    if source_type == "system_copy":  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=403,  # fcg-rewrite
            detail="System copy entity types cannot be deleted. They are automatically managed by the system.",  # fcg-rewrite
        )
    deleted = await _invoke(  # fcg-rewrite
        "Delete entity type",  # fcg-rewrite
        "Failed to delete entity type",  # fcg-rewrite
        lambda: engine.delete_entity_type(  # fcg-rewrite
            entity_type_id=entity_type_id,  # fcg-rewrite
            tenant_id=str(tenant.id),  # fcg-rewrite
            application_id=str(application_id) if application_id else None,  # fcg-rewrite
        ),
    )
    if not deleted:  # fcg-rewrite
        raise HTTPException(status_code=404, detail="Entity type not found or delete failed")  # fcg-rewrite
    logger.info("Entity type deleted: %s (type: %s) for user %s, app %s", entity_type_id, source_type, tenant.email, application_id)  # fcg-rewrite
    return {"success": True, "message": "Entity type deleted successfully"}  # fcg-rewrite


@router.post("/config/data-security/global-entity-types")  # fcg-rewrite
async def create_global_entity_type(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, application_id, engine = _scope(request, db)  # fcg-rewrite
    if not tenant.is_super_admin:  # fcg-rewrite
        raise HTTPException(status_code=403, detail="Only administrators can create global entity types")  # fcg-rewrite
    entity, _ = await _invoke(  # fcg-rewrite
        "Create global entity type",  # fcg-rewrite
        "Failed to create global entity type",  # fcg-rewrite
        lambda: _create_entity(engine, tenant, application_id, data, global_entity=True),  # fcg-rewrite
    )
    logger.info("Global entity type created: %s by admin %s", data.get("entity_type"), tenant.email)  # fcg-rewrite
    return {"success": True, "message": "Global entity type created successfully", "id": str(entity.id)}  # fcg-rewrite


async def _generate_regex(data: dict, request: Request, db: Session, method: str):  # fcg-rewrite
    tenant, _, engine = _scope(request, db)  # fcg-rewrite
    description = _required(data, "description", "Description")  # fcg-rewrite
    entity_type = data.get("entity_type", "")  # fcg-rewrite
    result = await _invoke(  # fcg-rewrite
        f"Generate {method.replace('_', ' ')}",  # fcg-rewrite
        f"Failed to generate {method.replace('_', ' ')}",  # fcg-rewrite
        lambda: getattr(engine, method)(description=description, entity_type=entity_type, sample_data=data.get("sample_data")),  # fcg-rewrite
    )
    logger.info("Generated %s for user %s, entity_type %s", method, tenant.email, entity_type)  # fcg-rewrite
    return result  # fcg-rewrite


@router.post("/config/data-security/generate-anonymization-regex")  # fcg-rewrite
async def generate_anonymization_regex(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _generate_regex(data, request, db, "generate_anonymization_regex")  # fcg-rewrite


@router.post("/config/data-security/test-anonymization")  # fcg-rewrite
async def test_anonymization(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, _, engine = _scope(request, db)  # fcg-rewrite
    method = _required(data, "method", "Method")  # fcg-rewrite
    test_input = _required(data, "test_input", "Test input")  # fcg-rewrite
    result = await _invoke(  # fcg-rewrite
        "Test anonymization",  # fcg-rewrite
        "Failed to test anonymization",  # fcg-rewrite
        lambda: engine.test_anonymization(method=method, config=data.get("config", {}), test_input=test_input),  # fcg-rewrite
    )
    logger.info("Tested anonymization for user %s, method %s", tenant.email, method)  # fcg-rewrite
    return result  # fcg-rewrite


@router.post("/config/data-security/generate-entity-type-code")  # fcg-rewrite
async def generate_entity_type_code(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, _, engine = _scope(request, db)  # fcg-rewrite
    name = _required(data, "entity_type_name", "Entity type name")  # fcg-rewrite
    result = await _invoke(  # fcg-rewrite
        "Generate entity type code",  # fcg-rewrite
        "Failed to generate entity type code",  # fcg-rewrite
        lambda: engine.generate_entity_type_code(entity_type_name=name),  # fcg-rewrite
    )
    logger.info("Generated entity type code for user %s, name %s", tenant.email, name)  # fcg-rewrite
    return result  # fcg-rewrite


@router.post("/config/data-security/generate-recognition-regex")  # fcg-rewrite
async def generate_recognition_regex(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _generate_regex(data, request, db, "generate_recognition_regex")  # fcg-rewrite


@router.post("/config/data-security/test-recognition-regex")  # fcg-rewrite
async def test_recognition_regex(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, _, engine = _scope(request, db)  # fcg-rewrite
    pattern = _required(data, "pattern", "Pattern")  # fcg-rewrite
    test_input = _required(data, "test_input", "Test input")  # fcg-rewrite
    result = await _invoke(  # fcg-rewrite
        "Test recognition regex",  # fcg-rewrite
        "Failed to test recognition regex",  # fcg-rewrite
        lambda: engine.test_recognition_regex(pattern=pattern, test_input=test_input),  # fcg-rewrite
    )
    logger.info("Tested recognition regex for user %s", tenant.email)  # fcg-rewrite
    return result  # fcg-rewrite


@router.post("/config/data-security/generate-genai-code")  # fcg-rewrite
async def generate_genai_code_standalone(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    from services.restore_anonymization_service import CodeGenerationError  # fcg-rewrite

    tenant, _, _ = _scope(request, db)  # fcg-rewrite
    _premium(tenant, db, SubscriptionFeature.GENAI_CODE_ANONYMIZATION)  # fcg-rewrite
    description = _required(data, "natural_description", "Natural language description")  # fcg-rewrite
    result = await _invoke(  # fcg-rewrite
        "Generate genai code",  # fcg-rewrite
        "Failed to generate code",  # fcg-rewrite
        lambda: _restore_service().generate_genai_anonymization_code(  # fcg-rewrite
            natural_description=description, sample_data=data.get("sample_data", "")  # fcg-rewrite
        ),
        invalid=(CodeGenerationError,),  # fcg-rewrite
    )
    logger.info("Generated genai code by user %s", tenant.email)  # fcg-rewrite
    return {"success": True, "code_generated": True, "genai_code": result["code"], "message": "Code generated successfully"}  # fcg-rewrite


@router.post("/config/data-security/test-genai-code")  # fcg-rewrite
async def test_genai_code_standalone(data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, _, _ = _scope(request, db)  # fcg-rewrite
    _premium(tenant, db, SubscriptionFeature.GENAI_CODE_ANONYMIZATION)  # fcg-rewrite
    code = _required(data, "code", "Code")  # fcg-rewrite
    test_input = _required(data, "test_input", "Test input")  # fcg-rewrite
    started = time()  # fcg-rewrite
    try:
        result = _restore_service().execute_genai_code(code=code, text=test_input)  # fcg-rewrite
        logger.info("Tested genai code by user %s", tenant.email)  # fcg-rewrite
        return {"success": True, "anonymized_text": result, "processing_time_ms": (time() - started) * 1000}  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as error:  # fcg-rewrite
        logger.error("Test genai code error: %s", error, exc_info=True)  # fcg-rewrite
        return {"success": False, "anonymized_text": "", "error": str(error), "processing_time_ms": 0}  # fcg-rewrite


@router.post("/config/data-security/entity-types/{entity_type_id}/generate-genai-code")  # fcg-rewrite
async def generate_genai_code(entity_type_id: str, data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    from services.restore_anonymization_service import CodeGenerationError  # fcg-rewrite

    tenant, _, _ = _scope(request, db)  # fcg-rewrite
    _premium(tenant, db, SubscriptionFeature.GENAI_CODE_ANONYMIZATION)  # fcg-rewrite
    description = _required(data, "natural_description", "Natural language description")  # fcg-rewrite
    entity = _owned_entity(db, entity_type_id, tenant)  # fcg-rewrite
    result = await _invoke(  # fcg-rewrite
        "Generate restore code",  # fcg-rewrite
        "Failed to generate restore code",  # fcg-rewrite
        lambda: _restore_service().generate_restore_code(  # fcg-rewrite
            entity_type_code=entity.entity_type,  # fcg-rewrite
            entity_type_name=entity.entity_type_name,  # fcg-rewrite
            natural_description=description,  # fcg-rewrite
            sample_data=data.get("sample_data", ""),  # fcg-rewrite
        ),
        invalid=(CodeGenerationError,),  # fcg-rewrite
    )
    entity.restore_code = result["code"]  # fcg-rewrite
    entity.restore_code_hash = result["code_hash"]  # fcg-rewrite
    entity.restore_natural_desc = description  # fcg-rewrite
    db.commit()  # fcg-rewrite
    logger.info("Generated restore code for entity type %s by user %s", entity_type_id, tenant.email)  # fcg-rewrite
    return {  # fcg-rewrite
        "success": True,  # fcg-rewrite
        "code_generated": True,  # fcg-rewrite
        "restore_code": result["code"],  # fcg-rewrite
        "placeholder_format": result["placeholder_format"],  # fcg-rewrite
        "message": "Code generated successfully",  # fcg-rewrite
    }


@router.post("/config/data-security/entity-types/{entity_type_id}/test-genai-code")  # fcg-rewrite
async def test_genai_code(entity_type_id: str, data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, _, _ = _scope(request, db)  # fcg-rewrite
    _premium(tenant, db, SubscriptionFeature.GENAI_CODE_ANONYMIZATION)  # fcg-rewrite
    test_input = _required(data, "test_input", "Test input")  # fcg-rewrite
    entity = _owned_entity(db, entity_type_id, tenant)  # fcg-rewrite
    if not entity.restore_code:  # fcg-rewrite
        raise HTTPException(status_code=400, detail="Restore code not generated yet. Please generate code first.")  # fcg-rewrite
    result = await _invoke(  # fcg-rewrite
        "Test restore anonymization",  # fcg-rewrite
        "Failed to test restore anonymization",  # fcg-rewrite
        lambda: _restore_service().test_restore_anonymization(  # fcg-rewrite
            text=test_input, entity_type_code=entity.entity_type, restore_code=entity.restore_code  # fcg-rewrite
        ),
    )
    logger.info("Tested restore anonymization for entity type %s by user %s", entity_type_id, tenant.email)  # fcg-rewrite
    return result  # fcg-rewrite


@router.put("/config/data-security/entity-types/{entity_type_id}/genai-code-config")  # fcg-rewrite
async def save_genai_code_config(entity_type_id: str, data: dict, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, _, _ = _scope(request, db)  # fcg-rewrite
    _premium(tenant, db, SubscriptionFeature.GENAI_CODE_ANONYMIZATION)  # fcg-rewrite
    entity = _owned_entity(db, entity_type_id, tenant)  # fcg-rewrite
    if data.get("natural_description"):  # fcg-rewrite
        entity.restore_natural_desc = data["natural_description"]  # fcg-rewrite
    db.commit()  # fcg-rewrite
    logger.info("Saved genai-code config for entity type %s by user %s", entity_type_id, tenant.email)  # fcg-rewrite
    return {"success": True, "message": "GenAI code configuration saved"}  # fcg-rewrite


@router.get("/config/data-security/feature-availability")  # fcg-rewrite
async def get_premium_feature_availability(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, _, _ = _scope(request, db)  # fcg-rewrite
    availability = await _invoke(  # fcg-rewrite
        "Get feature availability",  # fcg-rewrite
        "Failed to get feature availability",  # fcg-rewrite
        lambda: get_feature_availability(tenant_id=str(tenant.id), db=db),  # fcg-rewrite
    )
    logger.debug("Feature availability check for user %s: %s", tenant.email, availability)  # fcg-rewrite
    return availability  # fcg-rewrite
