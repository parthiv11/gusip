from contextlib import asynccontextmanager

import asyncio
import hmac

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, alerts, auth, cameras, cases, evidence, feeds, gis, ingest, integrations, search, watchlist, ws
from app.config import get_settings
from sqlalchemy import text
from app.db import Base, engine, SessionLocal
from app.services.event_bus import bus
from app.services.matching import collapse_duplicate_open_alerts

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import models  # noqa: F401

    if settings.app_env.lower() not in {"production", "prod"}:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS face_embedding JSONB"))
    async with SessionLocal() as db:
        await collapse_duplicate_open_alerts(db)
        await db.commit()
    if settings.app_env.lower() not in {"production", "prod"}:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_open_watchlist_camera "
                    "ON alerts (watchlist_id, camera_id) WHERE status = 'new'"
                )
            )
    await bus.connect()
    if settings.face_enabled:
        from app.services.face import warmup_arcface

        asyncio.create_task(asyncio.to_thread(warmup_arcface))
    relay_task = asyncio.create_task(ws.relay_redis())
    yield
    relay_task.cancel()
    await bus.close()
    await engine.dispose()


app = FastAPI(
    title="Gujarat Unified Surveillance Intelligence Platform",
    description="GUSIP PoC API — Gujarat Police Innovation Challenge 2026",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.cookies.get(settings.session_cookie_name):
        cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
        header_token = request.headers.get("x-csrf-token", "")
        if not cookie_token or not hmac.compare_digest(cookie_token, header_token):
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(cameras.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(gis.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(feeds.router, prefix="/api/v1")
app.include_router(ws.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gusip-api", "env": settings.app_env}


@app.get("/api/v1/meta")
async def meta():
    return {
        "name": "GUSIP",
        "version": "1.0.0",
        "hackathon": "Gujarat Police Innovation Challenge 2026",
        "architecture": "hybrid-federation",
        "poc_cameras": 50,
        "scale_target": 80000,
        "sentinel_enabled": settings.sentinel_enabled,
        "auth_provider": settings.auth_provider,
        "face": _face_status(),
    }


def _face_status() -> dict:
    from app.services.face import arcface_status

    return arcface_status()
