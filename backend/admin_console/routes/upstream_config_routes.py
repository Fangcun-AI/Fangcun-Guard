"""Tenant-level upstream model provider configuration."""

from contextlib import contextmanager
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.connection import get_admin_db_session
from database.models import OnlineTestModelSelection, Tenant, UpstreamApiConfig
from services.proxy_credentials import ProxyCredentialCipher
from utils.logger import setup_logger

router = APIRouter()
logger = setup_logger()
cipher = ProxyCredentialCipher()
_REASONING_FORMATS = {"auto", "field", "tag", "none"}


@contextmanager
def _database():
    db = get_admin_db_session()
    try:
        yield db
    finally:
        db.close()


def get_current_user_from_request(request: Request, db: Session) -> Tenant:
    auth_context = getattr(request.state, "auth_context", None)
    data = auth_context.get("data") if isinstance(auth_context, dict) else None
    if not data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    tenant_id = data.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant ID not found in auth context")
    try:
        tenant_uuid = UUID(str(tenant_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    tenant = db.query(Tenant).filter(Tenant.id == tenant_uuid).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _seal_api_key(api_key: str) -> str:
    return cipher.encrypt(api_key)


def _unseal_api_key(encrypted_api_key: str) -> str:
    return cipher.decrypt(encrypted_api_key)


def _obfuscate_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 10:
        return api_key[0] + "*" * (len(api_key) - 2) + api_key[-1] if len(api_key) > 2 else api_key
    return api_key[:6] + "*" * (len(api_key) - 10) + api_key[-4:]


def _gateway_url(config) -> str:
    return f"http://localhost:5002/v1/gateway/{config.id}/"


def _summary(config) -> dict:
    return {
        "id": str(config.id),
        "config_name": config.config_name,
        "api_base_url": config.api_base_url,
        "provider": config.provider,
        "is_active": config.is_active,
        "gateway_url": _gateway_url(config),
    }


def _full(config) -> dict:
    payload = _summary(config)
    payload.update(
        enable_reasoning_detection=config.enable_reasoning_detection,
        reasoning_format=config.reasoning_format or "auto",
        stream_chunk_size=config.stream_chunk_size,
        description=config.description,
        is_private_model=config.is_private_model if config.is_private_model is not None else False,
        is_default_private_model=config.is_default_private_model if config.is_default_private_model is not None else False,
        private_model_names=config.private_model_names if config.private_model_names is not None else [],
        default_private_model_name=config.default_private_model_name,
        created_at=config.created_at.isoformat(),
    )
    return payload


def _error(label: str, error: Exception):
    logger.error("%s error: %s", label, error)
    return JSONResponse(status_code=500, content={"success": False, "error": str(error)})


def _tenant_config(db: Session, tenant, api_id: str):
    config = (
        db.query(UpstreamApiConfig)
        .filter(UpstreamApiConfig.id == api_id, UpstreamApiConfig.tenant_id == tenant.id)
        .first()
    )
    if not config:
        raise ValueError("Upstream API configuration not found")
    return config


def _clear_default(db: Session, tenant_id, *, exclude=None) -> None:
    query = db.query(UpstreamApiConfig).filter(
        UpstreamApiConfig.tenant_id == tenant_id,
        UpstreamApiConfig.is_default_private_model == True,
    )
    if exclude is not None:
        query = query.filter(UpstreamApiConfig.id != exclude)
    query.update({UpstreamApiConfig.is_default_private_model: False})


@router.get("/proxy/upstream-apis")
async def get_user_upstream_apis(request: Request):
    try:
        with _database() as db:
            tenant = get_current_user_from_request(request, db)
            configs = db.query(UpstreamApiConfig).filter(UpstreamApiConfig.tenant_id == tenant.id).all()
            logger.info("Found %s upstream configs for tenant %s", len(configs), tenant.id)
            return {"success": True, "data": [_full(config) for config in configs]}
    except Exception as error:
        return _error("Get user upstream APIs", error)


@router.post("/proxy/upstream-apis")
async def create_upstream_api(request: Request):
    try:
        payload = await request.json()
        for field in ("config_name", "api_base_url", "api_key"):
            if not payload.get(field):
                raise ValueError(f"Missing required field: {field}")
        with _database() as db:
            tenant = get_current_user_from_request(request, db)
            duplicate = (
                db.query(UpstreamApiConfig)
                .filter(UpstreamApiConfig.tenant_id == tenant.id, UpstreamApiConfig.config_name == payload["config_name"])
                .first()
            )
            if duplicate:
                raise ValueError(f"Upstream API configuration '{payload['config_name']}' already exists")
            if payload.get("is_default_private_model"):
                _clear_default(db, tenant.id)
            config = UpstreamApiConfig(
                id=uuid4(),
                tenant_id=tenant.id,
                application_id=None,
                config_name=payload["config_name"],
                api_base_url=payload["api_base_url"],
                api_key_encrypted=_seal_api_key(payload["api_key"]),
                provider=payload.get("provider"),
                is_active=bool(payload.get("is_active", True)),
                enable_reasoning_detection=bool(payload.get("enable_reasoning_detection", True)),
                reasoning_format=payload.get("reasoning_format") if payload.get("reasoning_format") in _REASONING_FORMATS else "auto",
                stream_chunk_size=int(payload.get("stream_chunk_size", 50)),
                description=payload.get("description"),
                is_private_model=bool(payload.get("is_private_model", False)),
                is_default_private_model=bool(payload.get("is_default_private_model", False)),
                private_model_names=payload.get("private_model_names", []),
                default_private_model_name=payload.get("default_private_model_name"),
            )
            db.add(config)
            db.commit()
            db.refresh(config)
            return {"success": True, "data": _summary(config)}
    except Exception as error:
        return _error("Create upstream API", error)


@router.get("/proxy/upstream-apis/{api_id}")
async def get_upstream_api_detail(api_id: str, request: Request):
    try:
        with _database() as db:
            tenant = get_current_user_from_request(request, db)
            config = _tenant_config(db, tenant, api_id)
            payload = _full(config)
            try:
                payload["api_key_masked"] = _obfuscate_api_key(_unseal_api_key(config.api_key_encrypted)) if config.api_key_encrypted else ""
            except Exception as error:
                logger.error("Failed to decrypt API key: %s", error)
                payload["api_key_masked"] = "******"
            payload["is_active"] = config.is_active if config.is_active is not None else True
            payload["enable_reasoning_detection"] = (
                config.enable_reasoning_detection if config.enable_reasoning_detection is not None else True
            )
            payload["stream_chunk_size"] = config.stream_chunk_size if config.stream_chunk_size is not None else 50
            return {"success": True, "data": payload}
    except Exception as error:
        return _error("Get upstream API detail", error)


def _apply_updates(config, payload: dict) -> None:
    boolean_fields = {"is_active", "enable_reasoning_detection", "is_private_model", "is_default_private_model"}
    for field, value in payload.items():
        if field == "api_key":
            if value:
                config.api_key_encrypted = _seal_api_key(value)
        elif field in boolean_fields:
            setattr(config, field, bool(value))
        elif field == "reasoning_format":
            if value in _REASONING_FORMATS:
                config.reasoning_format = value
        elif field == "stream_chunk_size":
            config.stream_chunk_size = int(value)
        elif field == "private_model_names":
            config.private_model_names = value if isinstance(value, list) else []
        elif field == "default_private_model_name":
            config.default_private_model_name = value or None
        elif hasattr(config, field):
            setattr(config, field, value)


@router.put("/proxy/upstream-apis/{api_id}")
async def update_upstream_api(api_id: str, request: Request):
    try:
        payload = await request.json()
        with _database() as db:
            tenant = get_current_user_from_request(request, db)
            config = _tenant_config(db, tenant, api_id)
            if "config_name" in payload:
                duplicate = (
                    db.query(UpstreamApiConfig)
                    .filter(
                        UpstreamApiConfig.tenant_id == tenant.id,
                        UpstreamApiConfig.config_name == payload["config_name"],
                        UpstreamApiConfig.id != api_id,
                    )
                    .first()
                )
                if duplicate:
                    raise ValueError(f"Upstream API configuration '{payload['config_name']}' already exists")
            if payload.get("is_default_private_model"):
                _clear_default(db, tenant.id, exclude=api_id)
            _apply_updates(config, payload)
            db.commit()
            db.refresh(config)
            return {"success": True, "data": _summary(config)}
    except Exception as error:
        return _error("Update upstream API", error)


@router.delete("/proxy/upstream-apis/{api_id}")
async def delete_upstream_api(api_id: str, request: Request):
    try:
        with _database() as db:
            tenant = get_current_user_from_request(request, db)
            config = _tenant_config(db, tenant, api_id)
            deleted = db.query(OnlineTestModelSelection).filter(OnlineTestModelSelection.proxy_model_id == api_id).delete()
            name = config.config_name
            db.delete(config)
            db.commit()
            logger.info("Deleted upstream API config '%s' for tenant %s and %s model selections", name, tenant.id, deleted)
            return {"success": True}
    except Exception as error:
        return _error("Delete upstream API", error)
