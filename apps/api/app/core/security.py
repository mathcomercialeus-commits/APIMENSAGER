import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _fernet_instance() -> Fernet:
    digest = hashlib.sha256(settings.data_encryption_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet_instance().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet_instance().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Falha ao descriptografar segredo sensivel.") from exc


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not app_secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature_header.split("=", 1)[1], expected)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at, "typ": "access"}
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(subject: str) -> tuple[str, str, int]:
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    expires_at = datetime.now(timezone.utc) + expires_delta
    token_jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expires_at,
        "typ": "refresh",
        "jti": token_jti,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, token_jti, int(expires_delta.total_seconds())


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Token invalido ou expirado.") from exc
