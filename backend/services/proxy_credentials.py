"""Credential storage helpers for proxy and gateway integrations."""

import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

from config import settings


class ProxyCredentialCipher:
    """Read, initialize, and use the shared proxy encryption key."""

    def __init__(self, key_path: Optional[str] = None) -> None:
        self._key_path = Path(key_path or f"{settings.data_dir}/proxy_encryption.key")
        self._cipher = Fernet(self._load_or_create_key())

    def encrypt(self, plaintext: str) -> str:
        return self._cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._cipher.decrypt(ciphertext.encode()).decode()

    def _load_or_create_key(self) -> bytes:
        os.makedirs(self._key_path.parent, exist_ok=True)
        if self._key_path.exists():
            return self._key_path.read_bytes()

        key = Fernet.generate_key()
        self._key_path.write_bytes(key)
        return key
