from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from jose import JWTError, jwt

from app.config import get_settings
from app.core.crypto import decrypt_bytes
from app.services.storage import DATA_DIR

router = APIRouter(prefix="/evidence", tags=["evidence"])
settings = get_settings()


@router.get("/snapshots/{name}")
async def get_snapshot(name: str, token: str | None = Query(default=None)):
    if not token:
        raise HTTPException(401, "Token required")
    try:
        jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise HTTPException(401, "Invalid token")
    if "/" in name or ".." in name:
        raise HTTPException(400, "Invalid name")
    path = DATA_DIR / "snapshots" / name
    if not path.exists():
        raise HTTPException(404, "Not found")
    try:
        png = decrypt_bytes(path.read_bytes())
    except Exception as exc:
        raise HTTPException(500, f"Decrypt failed: {exc}") from exc
    return Response(content=png, media_type="image/png")
