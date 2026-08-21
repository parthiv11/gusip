from contextlib import asynccontextmanager

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, alerts, auth, cameras, cases, evidence, feeds, gis, ingest, integrations, search, watchlist, ws
from app.config import get_settings
from sqlalchemy import text
from app.db import Base, engine, SessionLocal
from app.services.event_bus import bus
from app.services.matching import collapse_duplicate_open_alerts

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        from app import models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await collapse_duplicate_open_alerts(db)
        await db.commit()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_open_watchlist_camera "
                "ON alerts (watchlist_id, camera_id) WHERE status = 'new'"
            )
        )
    await bus.connect()
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
    }
