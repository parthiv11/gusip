from datetime import datetime, timedelta, timezone
import asyncio
import time
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token", auto_error=False)
settings = get_settings()
_jwks_cache: tuple[float, dict[str, Any]] | None = None
_jwks_lock = asyncio.Lock()

ROLE_HIERARCHY = {
    "system_admin": 40,
    "department_coordinator": 30,
    "investigation_officer": 20,
    "control_room_operator": 10,
}


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def create_access_token(subject: str, role: str, department_id: int | None) -> str:
    if settings.auth_provider != "local":
        raise RuntimeError("Local token issuance is disabled for the configured auth provider")
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "dept": department_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


async def _oidc_jwks() -> dict[str, Any]:
    global _jwks_cache
    now = time.monotonic()
    if _jwks_cache and _jwks_cache[0] > now:
        return _jwks_cache[1]
    async with _jwks_lock:
        if _jwks_cache and _jwks_cache[0] > now:
            return _jwks_cache[1]
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.get(settings.oidc_jwks_url)
            response.raise_for_status()
            value = response.json()
        if not isinstance(value, dict) or not isinstance(value.get("keys"), list):
            raise JWTError("Invalid OIDC JWKS response")
        _jwks_cache = (now + 300, value)
        return value


async def decode_access_token(token: str) -> dict[str, Any]:
    if settings.auth_provider == "local":
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if header.get("alg") != "RS256" or not kid:
        raise JWTError("Unsupported OIDC token header")
    jwks = await _oidc_jwks()
    key = next((item for item in jwks["keys"] if item.get("kid") == kid and item.get("kty") == "RSA"), None)
    if key is None:
        raise JWTError("OIDC signing key not found")
    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer,
        options={"verify_at_hash": False},
    )


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = token or request.cookies.get(settings.session_cookie_name)
    if not token:
        raise credentials_exc
    try:
        payload = await decode_access_token(token)
        username = payload.get(settings.oidc_username_claim) if settings.auth_provider == "oidc" else payload.get("sub")
        if not username:
            raise credentials_exc
    except (JWTError, httpx.HTTPError):
        raise credentials_exc
    result = await db.execute(select(User).where(User.username == username, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    return user


def require_roles(*roles: str):
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles and user.role != "system_admin":
            raise HTTPException(status_code=403, detail="Insufficient privileges")
        return user

    return checker


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
