from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.core.crypto import encrypt_bytes

settings = get_settings()
DATA_DIR = Path("/app/data") if Path("/app/data").exists() else Path(__file__).resolve().parents[2] / "data"


def _ensure_dirs() -> None:
    (DATA_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "clips").mkdir(parents=True, exist_ok=True)


def save_snapshot_png(png_bytes: bytes, prefix: str = "snap") -> str:
    _ensure_dirs()
    encrypted = encrypt_bytes(png_bytes)
    name = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}.enc"
    path = DATA_DIR / "snapshots" / name
    path.write_bytes(encrypted)
    return f"/api/v1/evidence/snapshots/{name}"


def generate_placeholder_snapshot(label: str, plate: str | None, camera_code: str) -> bytes:
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (400, 240), (18, 22, 36))
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, 399, 28), fill=(212, 168, 75))
        draw.text((10, 8), f"GUSIP  {camera_code}", fill=(10, 12, 20))
        draw.text((10, 50), (label or "detection")[:42], fill=(230, 230, 230))
        if plate:
            draw.rectangle((40, 140, 360, 200), fill=(20, 20, 20))
            draw.text((55, 160), plate, fill=(250, 250, 250))
        from io import BytesIO

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return _tiny_png()


def _tiny_png() -> bytes:
    import base64

    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )
