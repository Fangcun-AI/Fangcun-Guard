"""Cryptography-backed RSA compatibility hooks for alipay-sdk-python."""

import base64
from typing import Union

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

TextOrBytes = Union[str, bytes]


def _bytes(value: TextOrBytes, charset: str = "utf-8") -> bytes:
    return value.encode(charset) if isinstance(value, str) else value


def sign_with_rsa2_cryptography(
    private_key_pem: TextOrBytes,
    sign_content: TextOrBytes,
    charset: str = "utf-8",
) -> str:
    private_key = serialization.load_pem_private_key(
        _bytes(private_key_pem, charset), password=None
    )
    signature = private_key.sign(
        _bytes(sign_content, charset), padding.PKCS1v15(), hashes.SHA256()
    )
    return base64.b64encode(signature).decode(charset)


def verify_with_rsa_cryptography(
    public_key_pem: TextOrBytes,
    sign_content: bytes,
    signature: str,
) -> bool:
    try:
        public_key = serialization.load_pem_public_key(_bytes(public_key_pem))
        public_key.verify(
            base64.b64decode(signature, validate=True),
            sign_content,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def apply_alipay_rsa_patch() -> bool:
    try:
        import alipay.aop.api.util.SignatureUtils as signature_utils
    except ImportError as exc:
        print(f"Could not apply Alipay RSA patch: {exc}")
        return False
    signature_utils.sign_with_rsa2 = sign_with_rsa2_cryptography
    signature_utils.verify_with_rsa = verify_with_rsa_cryptography
    return True
