"""Configuration endpoints for application-level policy registries."""

from inspect import isawaitable  # fcg-rewrite
from typing import List, Optional  # fcg-rewrite

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from admin_console.routes.upstream_config_routes import get_current_user_from_request  # fcg-rewrite
from config import settings  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from models.requests import BlacklistRequest, KnowledgeBaseRequest, ResponseTemplateRequest, WhitelistRequest  # fcg-rewrite
from models.responses import (  # fcg-rewrite
    ApiResponse,  # fcg-rewrite
    BlacklistResponse,  # fcg-rewrite
    KnowledgeBaseFileInfo,  # fcg-rewrite
    KnowledgeBaseResponse,  # fcg-rewrite
    ResponseTemplateResponse,  # fcg-rewrite
    SimilarQuestionResult,  # fcg-rewrite
    WhitelistResponse,  # fcg-rewrite
)
from services.application_request_context import resolve_admin_application_context  # fcg-rewrite
from services.config_knowledge_base_service import ConfigKnowledgeBaseService  # fcg-rewrite
from services.config_registry_service import ConfigRegistryService  # fcg-rewrite
from services.config_runtime_service import ConfigRuntimeService  # fcg-rewrite
from utils.logger import setup_logger  # fcg-rewrite

logger = setup_logger()  # fcg-rewrite
router = APIRouter(tags=["Configuration"])  # fcg-rewrite
public_router = APIRouter(tags=["Configuration - Public"])  # fcg-rewrite


def get_current_user_and_application_from_request(request: Request, db: Session):  # fcg-rewrite
    context = resolve_admin_application_context(request, db)  # fcg-rewrite
    return context.tenant, context.application_id  # fcg-rewrite


def get_config_registry_service(db: Session) -> ConfigRegistryService:  # fcg-rewrite
    return ConfigRegistryService(db)  # fcg-rewrite


def get_config_knowledge_base_service(db: Session) -> ConfigKnowledgeBaseService:  # fcg-rewrite
    return ConfigKnowledgeBaseService(db)  # fcg-rewrite


def get_config_runtime_service(db: Session) -> ConfigRuntimeService:  # fcg-rewrite
    return ConfigRuntimeService(db)  # fcg-rewrite


async def _execute(label, failure, operation, *, db: Optional[Session] = None, missing: bool = False):  # fcg-rewrite
    try:
        result = operation()  # fcg-rewrite
        return await result if isawaitable(result) else result  # fcg-rewrite
    except ValueError as error:  # fcg-rewrite
        if missing:  # fcg-rewrite
            raise HTTPException(status_code=404, detail=str(error))  # fcg-rewrite
        if db is not None:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
        logger.error("%s error: %s", label, error)  # fcg-rewrite
        detail = failure(error) if callable(failure) else failure  # fcg-rewrite
        raise HTTPException(status_code=500, detail=detail)  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception as error:  # fcg-rewrite
        if db is not None:  # fcg-rewrite
            db.rollback()  # fcg-rewrite
        logger.error("%s error: %s", label, error)  # fcg-rewrite
        detail = failure(error) if callable(failure) else failure  # fcg-rewrite
        raise HTTPException(status_code=500, detail=detail)  # fcg-rewrite


def _ok(subject: str, action: str) -> ApiResponse:  # fcg-rewrite
    return ApiResponse(success=True, message=f"{subject} {action} successfully")  # fcg-rewrite


async def _registry_read(request: Request, db: Session, operation, failure: str):  # fcg-rewrite
    _, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
    service = get_config_registry_service(db)  # fcg-rewrite
    return await _execute(f"Get {failure}", f"Failed to get {failure}", lambda: operation(service, application_id))  # fcg-rewrite


async def _registry_write(  # fcg-rewrite
    subject: str,  # fcg-rewrite
    action: str,  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session,  # fcg-rewrite
    operation,  # fcg-rewrite
    *,
    missing: bool = False,  # fcg-rewrite
):
    tenant, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
    service = get_config_registry_service(db)  # fcg-rewrite
    await _execute(  # fcg-rewrite
        f"{action.title()} {subject.lower()}",  # fcg-rewrite
        f"Failed to {action.lower()} {subject.lower()}",  # fcg-rewrite
        lambda: operation(service, tenant, application_id),  # fcg-rewrite
        missing=missing,  # fcg-rewrite
    )
    logger.info("%s %s for user %s, app %s", subject, action.lower(), tenant.email, application_id)  # fcg-rewrite
    return _ok(subject, f"{action.lower()}d" if action.endswith("e") else f"{action.lower()}ed")  # fcg-rewrite


async def _knowledge_result(request: Request, db: Session, operation, failure, *, rollback: bool = False):  # fcg-rewrite
    tenant, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
    service = get_config_knowledge_base_service(db)  # fcg-rewrite
    return await _execute(  # fcg-rewrite
        "Knowledge base operation",  # fcg-rewrite
        failure,  # fcg-rewrite
        lambda: operation(service, tenant, application_id),  # fcg-rewrite
        db=db if rollback else None,  # fcg-rewrite
    )


@router.get("/config/blacklist", response_model=List[BlacklistResponse])  # fcg-rewrite
async def get_blacklist(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_read(request, db, lambda service, app: service.list_blacklists(app), "blacklist")  # fcg-rewrite


@router.post("/config/blacklist", response_model=ApiResponse)  # fcg-rewrite
async def create_blacklist(payload: BlacklistRequest, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_write(  # fcg-rewrite
        "Blacklist", "Create", request, db, lambda service, tenant, app: service.create_blacklist(tenant, app, payload)  # fcg-rewrite
    )


@router.put("/config/blacklist/{blacklist_id}", response_model=ApiResponse)  # fcg-rewrite
async def update_blacklist(blacklist_id: int, payload: BlacklistRequest, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_write(  # fcg-rewrite
        "Blacklist", "Update", request, db, lambda service, _tenant, app: service.update_blacklist(app, blacklist_id, payload), missing=True  # fcg-rewrite
    )


@router.delete("/config/blacklist/{blacklist_id}", response_model=ApiResponse)  # fcg-rewrite
async def delete_blacklist(blacklist_id: int, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_write(  # fcg-rewrite
        "Blacklist", "Delete", request, db, lambda service, _tenant, app: service.delete_blacklist(app, blacklist_id), missing=True  # fcg-rewrite
    )


@router.get("/config/whitelist", response_model=List[WhitelistResponse])  # fcg-rewrite
async def get_whitelist(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_read(request, db, lambda service, app: service.list_whitelists(app), "whitelist")  # fcg-rewrite


@router.post("/config/whitelist", response_model=ApiResponse)  # fcg-rewrite
async def create_whitelist(payload: WhitelistRequest, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_write(  # fcg-rewrite
        "Whitelist", "Create", request, db, lambda service, tenant, app: service.create_whitelist(tenant, app, payload)  # fcg-rewrite
    )


@router.put("/config/whitelist/{whitelist_id}", response_model=ApiResponse)  # fcg-rewrite
async def update_whitelist(whitelist_id: int, payload: WhitelistRequest, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_write(  # fcg-rewrite
        "Whitelist", "Update", request, db, lambda service, _tenant, app: service.update_whitelist(app, whitelist_id, payload), missing=True  # fcg-rewrite
    )


@router.delete("/config/whitelist/{whitelist_id}", response_model=ApiResponse)  # fcg-rewrite
async def delete_whitelist(whitelist_id: int, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_write(  # fcg-rewrite
        "Whitelist", "Delete", request, db, lambda service, _tenant, app: service.delete_whitelist(app, whitelist_id), missing=True  # fcg-rewrite
    )


@router.get("/config/responses", response_model=List[ResponseTemplateResponse])  # fcg-rewrite
async def get_response_templates(  # fcg-rewrite
    request: Request,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
    scanner_type: Optional[str] = None,  # fcg-rewrite
    scanner_identifier: Optional[str] = None,  # fcg-rewrite
):
    return await _registry_read(  # fcg-rewrite
        request,  # fcg-rewrite
        db,
        lambda service, app: service.list_response_templates(app, scanner_type, scanner_identifier),  # fcg-rewrite
        "response templates",  # fcg-rewrite
    )


@router.post("/config/responses", response_model=ApiResponse)  # fcg-rewrite
async def create_response_template(payload: ResponseTemplateRequest, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_write(  # fcg-rewrite
        "Response template",  # fcg-rewrite
        "Create",  # fcg-rewrite
        request,  # fcg-rewrite
        db,
        lambda service, tenant, app: service.create_response_template(tenant, app, payload),  # fcg-rewrite
    )


@router.put("/config/responses/{template_id}", response_model=ApiResponse)  # fcg-rewrite
async def update_response_template(  # fcg-rewrite
    template_id: int, payload: ResponseTemplateRequest, request: Request, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    return await _registry_write(  # fcg-rewrite
        "Response template",  # fcg-rewrite
        "Update",  # fcg-rewrite
        request,  # fcg-rewrite
        db,
        lambda service, _tenant, app: service.update_response_template(app, template_id, payload),  # fcg-rewrite
        missing=True,  # fcg-rewrite
    )


@router.delete("/config/responses/{template_id}", response_model=ApiResponse)  # fcg-rewrite
async def delete_response_template(template_id: int, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _registry_write(  # fcg-rewrite
        "Response template",  # fcg-rewrite
        "Delete",  # fcg-rewrite
        request,  # fcg-rewrite
        db,
        lambda service, _tenant, app: service.delete_response_template(app, template_id),  # fcg-rewrite
        missing=True,  # fcg-rewrite
    )


@router.get("/config/cache-info")  # fcg-rewrite
async def get_cache_info(db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _execute("Get cache info", "Failed to get cache info", lambda: get_config_runtime_service(db).get_cache_info())  # fcg-rewrite


@router.post("/config/cache/refresh")  # fcg-rewrite
async def refresh_cache(db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _execute("Refresh cache", "Failed to refresh cache", lambda: get_config_runtime_service(db).refresh_all_caches())  # fcg-rewrite


@router.get("/config/knowledge-bases", response_model=List[KnowledgeBaseResponse])  # fcg-rewrite
async def get_knowledge_bases(category: Optional[str] = None, request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _knowledge_result(  # fcg-rewrite
        request, db, lambda service, tenant, app: service.list_knowledge_bases(tenant, app, category), "Failed to get knowledge bases"  # fcg-rewrite
    )


@router.post("/config/knowledge-bases", response_model=ApiResponse)  # fcg-rewrite
async def create_knowledge_base(  # fcg-rewrite
    file: UploadFile = File(...),  # fcg-rewrite
    category: str = Form(None),  # fcg-rewrite
    scanner_type: str = Form(None),  # fcg-rewrite
    scanner_identifier: str = Form(None),  # fcg-rewrite
    name: str = Form(...),  # fcg-rewrite
    description: str = Form(""),  # fcg-rewrite
    similarity_threshold: float = Form(0.7),  # fcg-rewrite
    is_active: bool = Form(True),  # fcg-rewrite
    is_global: bool = Form(False),  # fcg-rewrite
    request: Request = None,  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    content = await file.read()  # fcg-rewrite
    await _knowledge_result(  # fcg-rewrite
        request,  # fcg-rewrite
        db,
        lambda service, tenant, app: service.create_knowledge_base(  # fcg-rewrite
            tenant,
            app,
            file_content=content,  # fcg-rewrite
            original_filename=file.filename,  # fcg-rewrite
            category=category,  # fcg-rewrite
            scanner_type=scanner_type,  # fcg-rewrite
            scanner_identifier=scanner_identifier,  # fcg-rewrite
            name=name,  # fcg-rewrite
            description=description,  # fcg-rewrite
            similarity_threshold=similarity_threshold,  # fcg-rewrite
            is_active=is_active,  # fcg-rewrite
            is_global=is_global,  # fcg-rewrite
        ),
        lambda error: f"Failed to create knowledge base: {error}",  # fcg-rewrite
        rollback=True,  # fcg-rewrite
    )
    return _ok("Knowledge base", "created")  # fcg-rewrite


@router.get("/config/knowledge-bases/available-scanners", response_model=dict)  # fcg-rewrite
async def get_available_scanners_for_knowledge_base(request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _knowledge_result(  # fcg-rewrite
        request, db, lambda service, tenant, app: service.get_available_scanners(tenant, app), "Failed to get available scanners"  # fcg-rewrite
    )


@router.put("/config/knowledge-bases/{kb_id}", response_model=ApiResponse)  # fcg-rewrite
async def update_knowledge_base(kb_id: int, payload: KnowledgeBaseRequest, request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    await _knowledge_result(  # fcg-rewrite
        request, db, lambda service, tenant, app: service.update_knowledge_base(tenant, app, kb_id, payload), "Failed to update knowledge base", rollback=True  # fcg-rewrite
    )
    return _ok("Knowledge base", "updated")  # fcg-rewrite


@router.delete("/config/knowledge-bases/{kb_id}", response_model=ApiResponse)  # fcg-rewrite
async def delete_knowledge_base(kb_id: int, request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    await _knowledge_result(  # fcg-rewrite
        request, db, lambda service, tenant, app: service.delete_knowledge_base(tenant, app, kb_id), "Failed to delete knowledge base", rollback=True  # fcg-rewrite
    )
    return _ok("Knowledge base", "deleted")  # fcg-rewrite


@router.post("/config/knowledge-bases/{kb_id}/replace-file", response_model=ApiResponse)  # fcg-rewrite
async def replace_knowledge_base_file(kb_id: int, file: UploadFile = File(...), request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    content = await file.read()  # fcg-rewrite
    await _knowledge_result(  # fcg-rewrite
        request,  # fcg-rewrite
        db,
        lambda service, _tenant, app: service.replace_knowledge_base_file(app, kb_id, content, file.filename),  # fcg-rewrite
        lambda error: f"Failed to replace knowledge base file: {error}",  # fcg-rewrite
        rollback=True,  # fcg-rewrite
    )
    return _ok("Knowledge base file", "replaced")  # fcg-rewrite


@router.get("/config/knowledge-bases/{kb_id}/info", response_model=KnowledgeBaseFileInfo)  # fcg-rewrite
async def get_knowledge_base_info(kb_id: int, request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _knowledge_result(  # fcg-rewrite
        request, db, lambda service, _tenant, app: service.get_knowledge_base_info(app, kb_id), "Failed to get knowledge base info"  # fcg-rewrite
    )


@router.post("/config/knowledge-bases/{kb_id}/search", response_model=List[SimilarQuestionResult])  # fcg-rewrite
async def search_similar_questions(  # fcg-rewrite
    kb_id: int, query: str, top_k: Optional[int] = 5, request: Request = None, db: Session = Depends(get_admin_db)  # fcg-rewrite
):
    return await _knowledge_result(  # fcg-rewrite
        request,  # fcg-rewrite
        db,
        lambda service, _tenant, app: service.search_similar_questions(app, kb_id, query, top_k),  # fcg-rewrite
        "Failed to search similar questions",  # fcg-rewrite
    )


@router.get("/config/categories/{category}/knowledge-bases", response_model=List[KnowledgeBaseResponse])  # fcg-rewrite
async def get_knowledge_bases_by_category(category: str, request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return await _knowledge_result(  # fcg-rewrite
        request,  # fcg-rewrite
        db,
        lambda service, _tenant, app: service.list_knowledge_bases_by_category(app, category),  # fcg-rewrite
        "Failed to get knowledge bases by category",  # fcg-rewrite
    )


@router.post("/config/knowledge-bases/{kb_id}/toggle-disable", response_model=ApiResponse)  # fcg-rewrite
async def toggle_global_knowledge_base_disable(kb_id: int, request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant = get_current_user_from_request(request, db)  # fcg-rewrite
    service = get_config_knowledge_base_service(db)  # fcg-rewrite
    is_disabled = await _execute(  # fcg-rewrite
        "Toggle global knowledge base disable",  # fcg-rewrite
        "Failed to toggle global knowledge base disable status",  # fcg-rewrite
        lambda: service.toggle_global_knowledge_base_disable(tenant, kb_id),  # fcg-rewrite
        db=db,
    )
    return _ok("Global knowledge base", "disabled" if is_disabled else "enabled")  # fcg-rewrite


@router.get("/config/knowledge-bases/{kb_id}/is-disabled", response_model=dict)  # fcg-rewrite
async def check_global_knowledge_base_disabled(kb_id: int, request: Request = None, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant = get_current_user_from_request(request, db)  # fcg-rewrite
    return await _execute(  # fcg-rewrite
        "Check global knowledge base disabled",  # fcg-rewrite
        "Failed to check knowledge base disabled status",  # fcg-rewrite
        lambda: get_config_knowledge_base_service(db).check_global_knowledge_base_disabled(tenant, kb_id),  # fcg-rewrite
    )


@public_router.get("/config/system-info")  # fcg-rewrite
async def get_system_info():  # fcg-rewrite
    return {  # fcg-rewrite
        "deployment_mode": settings.deployment_mode,  # fcg-rewrite
        "is_saas_mode": settings.is_saas_mode,  # fcg-rewrite
        "is_enterprise_mode": settings.is_enterprise_mode,  # fcg-rewrite
        "version": settings.app_version,  # fcg-rewrite
        "app_name": settings.app_name,  # fcg-rewrite
        "api_domain": settings.api_domain,  # fcg-rewrite
    }


@router.get("/config/fixed-answer-templates")  # fcg-rewrite
async def get_fixed_answer_templates(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    _, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
    return await _execute(  # fcg-rewrite
        "Get fixed answer templates",  # fcg-rewrite
        "Failed to get fixed answer templates",  # fcg-rewrite
        lambda: get_config_runtime_service(db).get_fixed_answer_templates(application_id),  # fcg-rewrite
    )


@router.put("/config/fixed-answer-templates")  # fcg-rewrite
async def update_fixed_answer_templates(request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant, application_id = get_current_user_and_application_from_request(request, db)  # fcg-rewrite
    body = await request.json()  # fcg-rewrite
    await _execute(  # fcg-rewrite
        "Update fixed answer templates",  # fcg-rewrite
        "Failed to update fixed answer templates",  # fcg-rewrite
        lambda: get_config_runtime_service(db).update_fixed_answer_templates(tenant, application_id, body),  # fcg-rewrite
        db=db,
    )
    return _ok("Fixed answer templates", "updated")  # fcg-rewrite
