from contextlib import asynccontextmanager

import asyncio
import hmac
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api import admin, alerts, auth, cameras, cases, evidence, feeds, gis, ingest, integrations, search, watchlist, ws
from app.config import get_settings
from sqlalchemy import text
from app.db import Base, engine, SessionLocal
from app.core.logging import configure_logging, request_id_var
from app.core.metrics import REQUEST_LATENCY, REQUESTS_TOTAL, render_metrics
from app.services.event_bus import bus
from app.services.matching import collapse_duplicate_open_alerts

settings = get_settings()
configure_logging("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import models  # noqa: F401

    if settings.app_env.lower() not in {"production", "prod"}:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(text("ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS face_embedding JSONB"))
    async with SessionLocal() as db:
        from app.services.iam import ensure_builtin_roles

        await ensure_builtin_roles(db)
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


@app.middleware("http")
async def observability(request: Request, call_next):
    """Assigns/propagates a request ID (for cross-log correlation) and records
    Prometheus request-count/latency metrics. Registered last so it wraps
    every other middleware and runs first-in/last-out."""
    req_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(req_id)
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
    finally:
        request_id_var.reset(token)
    duration = time.perf_counter() - start
    route = request.scope.get("route")
    path_label = route.path if route is not None else request.url.path
    REQUESTS_TOTAL.labels(request.method, path_label, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path_label).observe(duration)
    response.headers["X-Request-ID"] = req_id
    return response


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
    """Liveness: is the process up. Does not touch dependencies — see /ready."""
    return {"status": "ok", "service": "gusip-api", "env": settings.app_env}


@app.get("/ready")
async def ready():
    """Readiness: can this instance actually serve traffic (DB + Redis reachable)."""
    checks: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — surfaced to the caller, not swallowed
        checks["database"] = f"error: {exc}"
    try:
        await bus.r.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"status": "ok" if ok else "unready", "checks": checks})


@app.get("/metrics")
async def metrics():
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


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
