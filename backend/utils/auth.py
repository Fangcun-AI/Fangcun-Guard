"""Authentication primitives shared by API surfaces."""

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def check_existing_password_strength(plain_password: str, hashed_password: str) -> bool:
    if not verify_password(plain_password, hashed_password):
        return False
    from utils.validators import is_password_strong

    return is_password_strong(plain_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def generate_api_key() -> str:
    alphabet = string.ascii_letters + string.digits
    return "sk-xxai-" + "".join(secrets.choice(alphabet) for _ in range(52))


def generate_reset_token() -> str:
    return secrets.token_urlsafe(48)[:64]


def authenticate_admin(username: str, password: str) -> bool:
    return (
        username == settings.super_admin_username
        and password == settings.super_admin_password
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise _unauthorized()
    subject = payload.get("sub")
    if subject is None:
        raise _unauthorized()
    role = payload.get("role", "user")
    if role == "admin":
        result = {"username": subject, "role": role}
        for key in ("tenant_id", "email"):
            if payload.get(key):
                result[key] = payload[key]
        return result
    tenant_id = payload.get("tenant_id") or payload.get("user_id") or subject
    return {
        "tenant_id": tenant_id,
        "user_id": tenant_id,
        "sub": subject,
        "email": payload.get("email"),
        "role": role,
        "is_super_admin": payload.get("is_super_admin", False),
    }
