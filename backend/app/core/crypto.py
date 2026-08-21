from __future__ import annotations

from cryptography.fernet import Fernet
from hashlib import sha256
import base64

from app.config import get_settings


def _fernet() -> Fernet:
    key = sha256(get_settings().encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    return _fernet().decrypt(data)
