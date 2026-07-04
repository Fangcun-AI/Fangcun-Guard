"""Account and tenant self-service endpoints."""

from datetime import timedelta  # fcg-rewrite
from typing import Optional  # fcg-rewrite
from uuid import UUID  # fcg-rewrite

from fastapi import APIRouter, Depends, HTTPException, Request, status  # fcg-rewrite
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # fcg-rewrite
from pydantic import BaseModel, EmailStr  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from config import settings  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from database.models import EmailVerification, Tenant  # fcg-rewrite
from services.admin_service import admin_service  # fcg-rewrite
from utils.auth import create_access_token, get_password_hash, verify_password, verify_token  # fcg-rewrite
from utils.email import generate_verification_code, get_verification_expiry, send_verification_email  # fcg-rewrite
from utils.user import (  # fcg-rewrite
    add_user,  # fcg-rewrite
    confirm_user_email,  # fcg-rewrite
    find_user_by_email,  # fcg-rewrite
    login_rate_ok,  # fcg-rewrite
    rotate_api_key,  # fcg-rewrite
    save_login_attempt,  # fcg-rewrite
)

router = APIRouter()  # fcg-rewrite
security = HTTPBearer()  # fcg-rewrite


class RegisterRequest(BaseModel):  # fcg-rewrite
    email: EmailStr  # fcg-rewrite
    password: str  # fcg-rewrite
    language: Optional[str] = "en"  # fcg-rewrite


class VerifyEmailRequest(BaseModel):  # fcg-rewrite
    email: EmailStr  # fcg-rewrite
    verification_code: str  # fcg-rewrite


class ResendCodeRequest(BaseModel):  # fcg-rewrite
    email: EmailStr  # fcg-rewrite
    language: Optional[str] = "en"  # fcg-rewrite


class LoginRequest(BaseModel):  # fcg-rewrite
    email: EmailStr  # fcg-rewrite
    password: str  # fcg-rewrite
    language: Optional[str] = None  # fcg-rewrite


class LoginResponse(BaseModel):  # fcg-rewrite
    access_token: str  # fcg-rewrite
    token_type: str  # fcg-rewrite
    expires_in: int  # fcg-rewrite
    api_key: str  # fcg-rewrite
    tenant_id: str  # fcg-rewrite
    is_super_admin: bool  # fcg-rewrite
    requires_password_change: bool = False  # fcg-rewrite
    password_message: Optional[str] = None  # fcg-rewrite


class UserInfo(BaseModel):  # fcg-rewrite
    id: str
    email: str  # fcg-rewrite
    api_key: str  # fcg-rewrite
    model_api_key: Optional[str]  # fcg-rewrite
    is_active: bool  # fcg-rewrite
    is_verified: bool  # fcg-rewrite
    is_super_admin: bool  # fcg-rewrite
    rate_limit: int  # fcg-rewrite
    language: str  # fcg-rewrite
    log_direct_model_access: bool  # fcg-rewrite


class ApiKeyResponse(BaseModel):  # fcg-rewrite
    api_key: str  # fcg-rewrite


class ModelApiKeyResponse(BaseModel):  # fcg-rewrite
    model_api_key: str  # fcg-rewrite


class ChangePasswordRequest(BaseModel):  # fcg-rewrite
    current_password: str  # fcg-rewrite
    new_password: str  # fcg-rewrite


class UpdateLanguageRequest(BaseModel):  # fcg-rewrite
    language: str  # fcg-rewrite


class UpdateLogDMARequest(BaseModel):  # fcg-rewrite
    log_direct_model_access: bool  # fcg-rewrite


def _verification_code(db: Session, email: str) -> str:  # fcg-rewrite
    code = generate_verification_code()  # fcg-rewrite
    db.add(
        EmailVerification(  # fcg-rewrite
            email=email,  # fcg-rewrite
            verification_code=code,  # fcg-rewrite
            expires_at=get_verification_expiry(),  # fcg-rewrite
        )
    )
    db.commit()  # fcg-rewrite
    return code  # fcg-rewrite


def _send_code(email: str, code: str, language: str, success: str, fallback: str) -> dict:  # fcg-rewrite
    try:
        send_verification_email(email, code, language)  # fcg-rewrite
        return {"message": success}  # fcg-rewrite
    except Exception:  # fcg-rewrite
        return {"message": fallback}  # fcg-rewrite


def _language(value: Optional[str], default: str = "en") -> str:  # fcg-rewrite
    return value if value in {"en", "zh"} else default  # fcg-rewrite


def _tenant_uuid(payload: dict) -> UUID:  # fcg-rewrite
    try:
        return UUID(str(payload.get("tenant_id") or payload.get("sub")))  # fcg-rewrite
    except (TypeError, ValueError):  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")  # fcg-rewrite


def get_current_user_from_token(  # fcg-rewrite
    credentials: HTTPAuthorizationCredentials = Depends(security),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
) -> Tenant:  # fcg-rewrite
    try:
        tenant = db.query(Tenant).filter(Tenant.id == _tenant_uuid(verify_token(credentials.credentials))).first()  # fcg-rewrite
    except HTTPException:  # fcg-rewrite
        raise
    except Exception:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")  # fcg-rewrite
    if not tenant or not tenant.is_active or not tenant.is_verified:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")  # fcg-rewrite
    return tenant  # fcg-rewrite


def _client(request: Request) -> tuple[str, str]:  # fcg-rewrite
    address = request.client.host if request.client else "unknown"  # fcg-rewrite
    return address, request.headers.get("user-agent", "")  # fcg-rewrite


def _record_login(db: Session, email: str, request: Request, successful: bool) -> None:  # fcg-rewrite
    address, user_agent = _client(request)  # fcg-rewrite
    save_login_attempt(db, email, address, user_agent, successful)  # fcg-rewrite


def _rate_limit(db: Session, tenant: Tenant) -> int:  # fcg-rewrite
    try:
        from services.rate_limit_service import RateLimitService  # fcg-rewrite

        config = RateLimitService(db).get_tenant_config(str(tenant.id))  # fcg-rewrite
        return config.rate_limit if config and config.is_active else 10  # fcg-rewrite
    except Exception:  # fcg-rewrite
        return 10  # fcg-rewrite


@router.post("/register")  # fcg-rewrite
def register(payload: RegisterRequest, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    from utils.email_validator import validate_enterprise_email  # fcg-rewrite

    valid, reason = validate_enterprise_email(payload.email)  # fcg-rewrite
    if not valid:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)  # fcg-rewrite
    if find_user_by_email(db, payload.email):  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")  # fcg-rewrite
    try:
        add_user(db, payload.email, payload.password, _language(payload.language))  # fcg-rewrite
        code = _verification_code(db, payload.email)  # fcg-rewrite
    except ValueError as error:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))  # fcg-rewrite
    except Exception:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create account")  # fcg-rewrite
    return _send_code(  # fcg-rewrite
        payload.email,  # fcg-rewrite
        code,
        _language(payload.language),  # fcg-rewrite
        "Registration successful. Please check your email for the verification code.",  # fcg-rewrite
        "Registration successful, but the verification email could not be sent. Please contact the administrator.",  # fcg-rewrite
    )


@router.post("/verify-email")  # fcg-rewrite
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    if not confirm_user_email(db, payload.email, payload.verification_code):  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")  # fcg-rewrite
    return {"message": "Email verified successfully"}  # fcg-rewrite


@router.post("/resend-verification-code")  # fcg-rewrite
def resend_verification_code(payload: ResendCodeRequest, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    tenant = find_user_by_email(db, payload.email)  # fcg-rewrite
    if not tenant:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")  # fcg-rewrite
    if tenant.is_verified:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already verified")  # fcg-rewrite
    try:
        code = _verification_code(db, payload.email)  # fcg-rewrite
    except Exception:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create verification code")  # fcg-rewrite
    return _send_code(  # fcg-rewrite
        payload.email,  # fcg-rewrite
        code,
        _language(payload.language),  # fcg-rewrite
        "Verification code sent successfully",  # fcg-rewrite
        "The verification email could not be sent. Please contact the administrator.",  # fcg-rewrite
    )


@router.post("/login", response_model=LoginResponse)  # fcg-rewrite
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    address, _ = _client(request)  # fcg-rewrite
    if not login_rate_ok(db, payload.email, address):  # fcg-rewrite
        _record_login(db, payload.email, request, False)  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")  # fcg-rewrite
    tenant = find_user_by_email(db, payload.email)  # fcg-rewrite
    if not tenant or not verify_password(payload.password, tenant.password_hash):  # fcg-rewrite
        _record_login(db, payload.email, request, False)  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")  # fcg-rewrite
    if not tenant.is_active or not tenant.is_verified:  # fcg-rewrite
        _record_login(db, payload.email, request, False)  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive or unverified")  # fcg-rewrite

    from utils.password_validator import check_existing_password_strength  # fcg-rewrite

    requires_change, password_message = check_existing_password_strength(payload.password)  # fcg-rewrite
    if payload.language in {"en", "zh"}:  # fcg-rewrite
        tenant.language = payload.language  # fcg-rewrite
        db.commit()  # fcg-rewrite
    _record_login(db, payload.email, request, True)  # fcg-rewrite
    expires = timedelta(minutes=settings.access_token_expire_minutes)  # fcg-rewrite
    is_super_admin = admin_service.is_super_admin(tenant.email)  # fcg-rewrite
    tenant_id = str(tenant.id)  # fcg-rewrite
    token = create_access_token(  # fcg-rewrite
        {
            "sub": tenant_id,  # fcg-rewrite
            "tenant_id": tenant_id,  # fcg-rewrite
            "user_id": tenant_id,  # fcg-rewrite
            "email": tenant.email,  # fcg-rewrite
            "is_super_admin": is_super_admin,  # fcg-rewrite
        },
        expires,  # fcg-rewrite
    )
    return LoginResponse(  # fcg-rewrite
        access_token=token,  # fcg-rewrite
        token_type="bearer",  # fcg-rewrite
        expires_in=int(expires.total_seconds()),  # fcg-rewrite
        api_key=tenant.api_key,  # fcg-rewrite
        tenant_id=tenant_id,  # fcg-rewrite
        is_super_admin=is_super_admin,  # fcg-rewrite
        requires_password_change=requires_change,  # fcg-rewrite
        password_message=password_message,  # fcg-rewrite
    )


@router.get("/me", response_model=UserInfo)  # fcg-rewrite
def get_me(tenant: Tenant = Depends(get_current_user_from_token), db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return UserInfo(  # fcg-rewrite
        id=str(tenant.id),  # fcg-rewrite
        email=tenant.email,  # fcg-rewrite
        api_key=tenant.api_key,  # fcg-rewrite
        model_api_key=tenant.model_api_key,  # fcg-rewrite
        is_active=tenant.is_active,  # fcg-rewrite
        is_verified=tenant.is_verified,  # fcg-rewrite
        is_super_admin=admin_service.is_super_admin(tenant.email),  # fcg-rewrite
        rate_limit=_rate_limit(db, tenant),  # fcg-rewrite
        language=tenant.language or "en",  # fcg-rewrite
        log_direct_model_access=tenant.log_direct_model_access,  # fcg-rewrite
    )


@router.post("/regenerate-api-key", response_model=ApiKeyResponse)  # fcg-rewrite
def regenerate_api_key(tenant: Tenant = Depends(get_current_user_from_token), db: Session = Depends(get_admin_db)):  # fcg-rewrite
    return ApiKeyResponse(api_key=rotate_api_key(db, tenant))  # fcg-rewrite


@router.post("/regenerate-model-api-key", response_model=ModelApiKeyResponse)  # fcg-rewrite
def regenerate_model_api_key(tenant: Tenant = Depends(get_current_user_from_token), db: Session = Depends(get_admin_db)):  # fcg-rewrite
    import secrets  # fcg-rewrite

    tenant.model_api_key = f"sk-xxai-model-{secrets.token_hex(24)}"  # fcg-rewrite
    db.commit()  # fcg-rewrite
    return ModelApiKeyResponse(model_api_key=tenant.model_api_key)  # fcg-rewrite


@router.post("/logout")  # fcg-rewrite
def logout():  # fcg-rewrite
    return {"message": "Logged out successfully"}  # fcg-rewrite


@router.post("/change-password")  # fcg-rewrite
def change_password(  # fcg-rewrite
    payload: ChangePasswordRequest,  # fcg-rewrite
    tenant: Tenant = Depends(get_current_user_from_token),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    if not verify_password(payload.current_password, tenant.password_hash):  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")  # fcg-rewrite
    from utils.password_validator import validate_password_strength  # fcg-rewrite

    valid, message = validate_password_strength(payload.new_password)  # fcg-rewrite
    if not valid:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)  # fcg-rewrite
    tenant.password_hash = get_password_hash(payload.new_password)  # fcg-rewrite
    db.commit()  # fcg-rewrite
    return {"message": "Password changed successfully"}  # fcg-rewrite


@router.put("/language")  # fcg-rewrite
def update_language(  # fcg-rewrite
    payload: UpdateLanguageRequest,  # fcg-rewrite
    tenant: Tenant = Depends(get_current_user_from_token),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    if payload.language not in {"en", "zh"}:  # fcg-rewrite
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language")  # fcg-rewrite
    tenant.language = payload.language  # fcg-rewrite
    db.commit()  # fcg-rewrite
    return {"message": "Language updated successfully", "language": tenant.language}  # fcg-rewrite


@router.put("/log-direct-model-access")  # fcg-rewrite
def update_direct_model_logging(  # fcg-rewrite
    payload: UpdateLogDMARequest,  # fcg-rewrite
    tenant: Tenant = Depends(get_current_user_from_token),  # fcg-rewrite
    db: Session = Depends(get_admin_db),  # fcg-rewrite
):
    tenant.log_direct_model_access = payload.log_direct_model_access  # fcg-rewrite
    db.commit()  # fcg-rewrite
    return {"message": "Direct model access logging updated successfully"}  # fcg-rewrite
