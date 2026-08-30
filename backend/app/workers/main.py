"""Intelligence worker: feed health + simulated (or YOLO) detections into the federation bus."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models.camera import Camera
from app.seed import seed
from app.services.event_bus import bus
from app.services.matching import collapse_duplicate_open_alerts
from app.workers.adapters import get_adapter
from app.workers.simulator import Simulator
from app.workers.inference import inference_available, yolo_preview_loop
from app.workers.sentinel import anpr_loop, sync_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gusip.worker")
settings = get_settings()
HEARTBEAT_PATH = Path("/tmp/gusip-worker-heartbeat")


async def heartbeat_loop() -> None:
    while True:
        HEARTBEAT_PATH.write_text(datetime.now(timezone.utc).isoformat())
        await asyncio.sleep(10)


async def health_loop() -> None:
    rng = random.Random()
    while True:
        async with SessionLocal() as db:
            cams = list((await db.execute(select(Camera).where(Camera.is_active.is_(True)))).scalars())
            for cam in cams:
                if cam.source_type == "sentinel":
                    continue
                adapter = get_adapter(cam.source_type)
                status = await adapter.health(
                    {
                        "rtsp_url": cam.rtsp_url,
                        "onvif_endpoint": cam.onvif_endpoint,
                        "vendor_api_ref": cam.vendor_api_ref,
                        "vendor": cam.vendor,
                    }
                )
                # Rare transient disconnects to demonstrate auto-reconnect (FR-2.3 / NFR-3)
                if rng.random() < 0.02:
                    cam.status = "offline"
                else:
                    cam.status = status
                    cam.last_seen_at = datetime.now(timezone.utc)
            await db.commit()
        await asyncio.sleep(15)


async def sim_loop() -> None:
    sim = Simulator()
    while True:
        try:
            async with SessionLocal() as db:
                codes = await sim.step(db)
            log.info("sim tick emitted on %s cameras", len(codes))
        except Exception:
            log.exception("simulator step failed")
        await asyncio.sleep(4)


async def main() -> None:
    if settings.app_env.lower() not in {"production", "prod"}:
        await seed()
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
        log.info("ArcFace warmup scheduled")
    log.info("GUSIP worker started mode=%s kafka=%s sentinel=%s", settings.inference_mode, settings.use_kafka, settings.sentinel_enabled)
    tasks = [asyncio.create_task(heartbeat_loop()), asyncio.create_task(health_loop())]
    if settings.simulation_enabled:
        tasks.append(asyncio.create_task(sim_loop()))
    if settings.sentinel_enabled:
        tasks.append(asyncio.create_task(sync_loop()))
        if settings.sentinel_anpr_enabled:
            tasks.append(asyncio.create_task(anpr_loop()))
    if inference_available() and not (settings.sentinel_enabled and settings.sentinel_anpr_enabled):
        tasks.append(asyncio.create_task(yolo_preview_loop()))
        log.info("YOLO loop enabled")
    elif inference_available():
        log.info("YOLO on live Sentinel PTS samples (preview loop off)")
    else:
        log.warning("YOLO loop off (mode=%s, ultralytics missing?)", settings.inference_mode)
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
