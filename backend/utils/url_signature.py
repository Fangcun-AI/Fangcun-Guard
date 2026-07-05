"""Signed URL helpers for tenant media assets."""

import hashlib
import hmac
import time
from urllib.parse import quote

from config import settings


def _signature(tenant_id: str, filename: str, expires: int) -> str:
    payload = f"{tenant_id}|{filename}|{expires}".encode()
    return hmac.new(settings.jwt_secret_key.encode(), payload, hashlib.sha256).hexdigest()


def generate_media_url_signature(
    tenant_id: str,
    filename: str,
    expires_in_seconds: int = 3600,
) -> tuple[str, int]:
    expires = int(time.time()) + expires_in_seconds
    return _signature(tenant_id, filename, expires), expires


def verify_media_url_signature(
    tenant_id: str,
    filename: str,
    signature: str,
    expires: int,
) -> bool:
    if int(time.time()) > expires:
        return False
    return hmac.compare_digest(signature, _signature(tenant_id, filename, expires))


def generate_signed_media_url(
    tenant_id: str,
    filename: str,
    base_url: str = "/api/v1/media/image",
    expires_in_seconds: int = 3600,
) -> str:
    signature, expires = generate_media_url_signature(
        tenant_id, filename, expires_in_seconds
    )
    return (
        f"{base_url.rstrip('/')}/{quote(tenant_id, safe='')}/{quote(filename, safe='')}"
        f"?token={signature}&expires={expires}"
    )
