from datetime import timedelta, datetime  # fcg-rewrite
from fastapi import APIRouter, HTTPException, status, Depends  # fcg-rewrite
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # fcg-rewrite
from pydantic import BaseModel, EmailStr  # fcg-rewrite
from typing import Optional  # fcg-rewrite
from sqlalchemy.orm import Session  # fcg-rewrite

from utils.auth import authenticate_admin, create_access_token, verify_token, generate_reset_token, get_password_hash  # fcg-rewrite
from utils.email import send_password_reset_email, get_reset_token_expiry  # fcg-rewrite
from database.connection import get_admin_db  # fcg-rewrite
from database.models import Tenant, PasswordResetToken  # fcg-rewrite
from config import settings  # fcg-rewrite

router = APIRouter(tags=["Authentication"])  # fcg-rewrite
security = HTTPBearer()  # fcg-rewrite

class DefaultLanguageResponse(BaseModel):  # fcg-rewrite
    default_language: str  # fcg-rewrite

class LoginRequest(BaseModel):  # fcg-rewrite
    username: str  # fcg-rewrite
    password: str  # fcg-rewrite

class LoginResponse(BaseModel):  # fcg-rewrite
    access_token: str  # fcg-rewrite
    token_type: str  # fcg-rewrite
    expires_in: int  # fcg-rewrite

class UserInfo(BaseModel):  # fcg-rewrite
    username: str  # fcg-rewrite
    role: str  # fcg-rewrite

@router.get("/default-language", response_model=DefaultLanguageResponse)  # fcg-rewrite
async def get_default_language():  # fcg-rewrite
    """
    Get default language configuration for the platform.
    This is a public endpoint that doesn't require authentication.
    Used by frontend to initialize language when there's no stored preference.
    """
    return DefaultLanguageResponse(default_language=settings.default_language)  # fcg-rewrite

@router.post("/login", response_model=LoginResponse)  # fcg-rewrite
async def login(login_data: LoginRequest, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    """Admin login"""
    if not authenticate_admin(login_data.username, login_data.password):  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_401_UNAUTHORIZED,  # fcg-rewrite
            detail="Incorrect username or password",  # fcg-rewrite
            headers={"WWW-Authenticate": "Bearer"},  # fcg-rewrite
        )

    # Get admin user tenant_id from database
    from database.models import Tenant  # fcg-rewrite
    admin_user = db.query(Tenant).filter(Tenant.email == login_data.username).first()  # fcg-rewrite
    if not admin_user:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_401_UNAUTHORIZED,  # fcg-rewrite
            detail="Admin user not found in database",  # fcg-rewrite
            headers={"WWW-Authenticate": "Bearer"},  # fcg-rewrite
        )

    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)  # fcg-rewrite
    access_token = create_access_token(  # fcg-rewrite
        data={
            "sub": login_data.username,  # fcg-rewrite
            "role": "admin",  # fcg-rewrite
            "tenant_id": str(admin_user.id),  # fcg-rewrite
            "email": admin_user.email  # fcg-rewrite
        },
        expires_delta=access_token_expires  # fcg-rewrite
    )

    return LoginResponse(  # fcg-rewrite
        access_token=access_token,  # fcg-rewrite
        token_type="bearer",  # fcg-rewrite
        expires_in=settings.jwt_access_token_expire_minutes * 60  # fcg-rewrite
    )

@router.get("/me", response_model=UserInfo)  # fcg-rewrite
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):  # fcg-rewrite
    """Get current user information"""
    user_data = verify_token(credentials.credentials)  # fcg-rewrite
    # Compatible with different token structures: username field or sub field
    username = user_data.get("username") or user_data.get("sub")  # fcg-rewrite
    role = user_data.get("role", "admin")  # fcg-rewrite
    return UserInfo(username=username, role=role)  # fcg-rewrite

@router.post("/logout")  # fcg-rewrite
async def logout():  # fcg-rewrite
    """User logout (frontend handles token clearance)"""
    return {"message": "Successfully logged out"}  # fcg-rewrite

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:  # fcg-rewrite
    """Get current admin user (for dependency injection)"""
    return verify_token(credentials.credentials)  # fcg-rewrite

class ForgotPasswordRequest(BaseModel):  # fcg-rewrite
    email: EmailStr  # fcg-rewrite
    language: Optional[str] = 'en'  # fcg-rewrite

class ResetPasswordRequest(BaseModel):  # fcg-rewrite
    token: str  # fcg-rewrite
    new_password: str  # fcg-rewrite

@router.post("/forgot-password")  # fcg-rewrite
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    """Request password reset - send reset email"""
    # Check if user exists
    user = db.query(Tenant).filter(Tenant.email == request.email).first()  # fcg-rewrite

    # For security reasons, always return success even if email doesn't exist
    # This prevents email enumeration attacks
    if not user:  # fcg-rewrite
        return {"message": "If the email exists, a password reset link will be sent"}  # fcg-rewrite

    # Generate reset token
    reset_token = generate_reset_token()  # fcg-rewrite
    expires_at = get_reset_token_expiry()  # fcg-rewrite

    # Save reset token to database
    password_reset = PasswordResetToken(  # fcg-rewrite
        email=request.email,  # fcg-rewrite
        reset_token=reset_token,  # fcg-rewrite
        expires_at=expires_at,  # fcg-rewrite
        is_used=False  # fcg-rewrite
    )
    db.add(password_reset)  # fcg-rewrite
    db.commit()  # fcg-rewrite

    # Build reset URL
    reset_url = f"{settings.frontend_url}/platform/reset-password?token={reset_token}"  # fcg-rewrite

    # Send reset email
    try:
        send_password_reset_email(request.email, reset_url, request.language)  # fcg-rewrite
    except Exception as e:  # fcg-rewrite
        # Log error but don't expose it to user
        print(f"Failed to send password reset email: {e}")  # fcg-rewrite
        # Still return success to prevent email enumeration

    return {"message": "If the email exists, a password reset link will be sent"}  # fcg-rewrite

@router.post("/reset-password")  # fcg-rewrite
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    """Reset password using token"""
    # Find valid reset token
    reset_record = db.query(PasswordResetToken).filter(  # fcg-rewrite
        PasswordResetToken.reset_token == request.token,  # fcg-rewrite
        PasswordResetToken.is_used == False,  # fcg-rewrite
        PasswordResetToken.expires_at > datetime.utcnow()  # fcg-rewrite
    ).first()  # fcg-rewrite

    if not reset_record:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail="Invalid or expired reset token"  # fcg-rewrite
        )

    # Find user
    user = db.query(Tenant).filter(Tenant.email == reset_record.email).first()  # fcg-rewrite
    if not user:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_404_NOT_FOUND,  # fcg-rewrite
            detail="User not found"  # fcg-rewrite
        )

    # Validate new password strength
    from utils.validators import validate_password_strength  # fcg-rewrite
    password_validation = validate_password_strength(request.new_password)  # fcg-rewrite

    if not password_validation["is_valid"]:  # fcg-rewrite
        error_messages = ", ".join(password_validation["errors"])  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail=f"Password does not meet security requirements: {error_messages}"  # fcg-rewrite
        )

    # Update password
    user.password_hash = get_password_hash(request.new_password)  # fcg-rewrite

    # Mark token as used
    reset_record.is_used = True  # fcg-rewrite

    db.commit()  # fcg-rewrite

    return {"message": "Password reset successful"}  # fcg-rewrite

@router.post("/verify-reset-token")  # fcg-rewrite
async def verify_reset_token(token: str, db: Session = Depends(get_admin_db)):  # fcg-rewrite
    """Verify if reset token is valid"""
    reset_record = db.query(PasswordResetToken).filter(  # fcg-rewrite
        PasswordResetToken.reset_token == token,  # fcg-rewrite
        PasswordResetToken.is_used == False,  # fcg-rewrite
        PasswordResetToken.expires_at > datetime.utcnow()  # fcg-rewrite
    ).first()  # fcg-rewrite

    if not reset_record:  # fcg-rewrite
        raise HTTPException(  # fcg-rewrite
            status_code=status.HTTP_400_BAD_REQUEST,  # fcg-rewrite
            detail="Invalid or expired reset token"  # fcg-rewrite
        )

    return {"valid": True, "email": reset_record.email}  # fcg-rewrite
