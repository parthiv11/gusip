"""Force a stolen-vehicle multi-camera hop for live demo (Ahmedabad → Gandhinagar)."""

from __future__ import annotations

import asyncio
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models.camera import Camera
from app.services.event_bus import bus
from app.services.pipeline import ingest_detection
from app.workers.simulator import STOLEN_ROUTE


async def run() -> None:
    await bus.connect()
    async with SessionLocal() as db:
        cams = {c.code: c for c in (await db.execute(select(Camera))).scalars()}
    print("Demo scenario: stolen Fortuner GJ 01 ST 0001")
    t0 = time.perf_counter()
    for code in STOLEN_ROUTE:
        cam = cams[code]
        async with SessionLocal() as db:
            await ingest_detection(
                db,
                {
                    "camera_id": cam.id,
                    "event_type": "anpr",
                    "object_type": "vehicle",
                    "plate_number": "GJ 01 ST 0001",
                    "confidence": 0.96,
                    "attributes": {
                        "color": "white",
                        "vehicle_class": "suv",
                        "make": "Toyota",
                        "sim_tag": "stolen-fortuner",
                        "source_type": cam.source_type,
                    },
                    "bbox": {"x": 80, "y": 60, "w": 120, "h": 70},
                },
            )
        hop_ms = (time.perf_counter() - t0) * 1000
        print(f"  hop {code:12}  +{hop_ms:.0f} ms")
        await asyncio.sleep(1.2)
    print(f"End-to-end hops complete in {(time.perf_counter() - t0):.2f}s (target alert < 8s)")
    await bus.close()


if __name__ == "__main__":
    asyncio.run(run())
