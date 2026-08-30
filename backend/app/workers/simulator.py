"""Statewide traffic simulator: vehicles + persons moving across federated cameras."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera
from app.services.face import canned_embedding
from app.services.pipeline import ingest_detection

# Stolen vehicle corridor: Ahmedabad west -> north -> Gandhinagar link
STOLEN_ROUTE = ["AMD-SG-01", "AMD-SG-02", "AMD-TH-01", "GNR-HW-01", "GNR-IN-01"]
BLACKLIST_ROUTE = ["SRT-VR-01", "SRT-UC-01", "SRT-HW-01"]
WANTED_ROUTE = ["AMD-SG-01", "AMD-SK-01", "AMD-VS-01"]

COLORS = ["white", "black", "silver", "red", "blue", "grey"]
CLASSES = ["sedan", "suv", "hatchback", "two-wheeler", "lcv", "bus"]
MAKES = ["Maruti", "Hyundai", "Tata", "Honda", "Mahindra", "Toyota"]


def _plate(rng: random.Random, rto: str = "01") -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(2))
    num = rng.randint(1000, 9999)
    return f"GJ {rto} {letters} {num}"


class Simulator:
    def __init__(self) -> None:
        self.tick = 0
        self.rng = random.Random(2026)
        self.cameras: dict[str, Camera] = {}
        self.stolen_idx = 0
        self.black_idx = 0
        self.wanted_idx = 0

    async def load(self, db: AsyncSession) -> None:
        rows = (await db.execute(select(Camera).where(Camera.is_active.is_(True), Camera.source_type != "sentinel"))).scalars()
        self.cameras = {c.code: c for c in rows}

    async def step(self, db: AsyncSession) -> list[str]:
        if not self.cameras:
            await self.load(db)
        self.tick += 1
        emitted: list[str] = []

        # Background traffic on random cameras
        sample = self.rng.sample(list(self.cameras.values()), k=min(8, len(self.cameras)))
        for cam in sample:
            obj = "two-wheeler" if self.rng.random() < 0.35 else "vehicle"
            plate = _plate(self.rng, rto=self.rng.choice(["01", "05", "06", "18", "27"]))
            payload = self._det(
                cam,
                object_type=obj,
                plate=None if obj == "two-wheeler" and self.rng.random() < 0.4 else plate,
                attrs={
                    "color": self.rng.choice(COLORS),
                    "vehicle_class": "two-wheeler" if obj == "two-wheeler" else self.rng.choice(CLASSES),
                    "make": self.rng.choice(MAKES),
                    "source_type": cam.source_type,
                },
            )
            await ingest_detection(db, payload)
            emitted.append(cam.code)

        # Scripted watchlist tracks every few ticks
        if self.tick % 4 == 1:
            emitted.append(await self._scripted(db, STOLEN_ROUTE, self.stolen_idx, self._stolen_payload))
            self.stolen_idx = (self.stolen_idx + 1) % len(STOLEN_ROUTE)
        if self.tick % 6 == 2:
            emitted.append(await self._scripted(db, BLACKLIST_ROUTE, self.black_idx, self._black_payload))
            self.black_idx = (self.black_idx + 1) % len(BLACKLIST_ROUTE)
        if self.tick % 7 == 3:
            emitted.append(await self._scripted(db, WANTED_ROUTE, self.wanted_idx, self._wanted_payload))
            self.wanted_idx = (self.wanted_idx + 1) % len(WANTED_ROUTE)

        return [e for e in emitted if e]

    async def _scripted(self, db: AsyncSession, route: list[str], idx: int, factory) -> str:
        code = route[idx]
        cam = self.cameras.get(code)
        if not cam:
            return ""
        await ingest_detection(db, factory(cam))
        return code

    def _stolen_payload(self, cam: Camera) -> dict[str, Any]:
        return self._det(
            cam,
            object_type="vehicle",
            plate="GJ 01 ST 0001",
            attrs={
                "color": "white",
                "vehicle_class": "suv",
                "make": "Toyota",
                "sim_tag": "stolen-fortuner",
                "source_type": cam.source_type,
            },
            confidence=0.94,
        )

    def _black_payload(self, cam: Camera) -> dict[str, Any]:
        return self._det(
            cam,
            object_type="vehicle",
            plate="GJ 05 BL 9999",
            attrs={
                "color": "black",
                "vehicle_class": "sedan",
                "make": "Honda",
                "sim_tag": "blacklist-city",
                "source_type": cam.source_type,
            },
            confidence=0.91,
        )

    def _wanted_payload(self, cam: Camera) -> dict[str, Any]:
        payload = self._det(
            cam,
            object_type="person",
            plate=None,
            attrs={
                "clothing": "grey hoodie",
                "watch_tag": "wanted-rakesh",
                "source_type": cam.source_type,
                "face_engine": "canned",
            },
            confidence=0.86,
        )
        payload["embedding"] = canned_embedding("wanted-rakesh")
        return payload

    def _det(self, cam: Camera, object_type: str, plate: str | None, attrs: dict, confidence: float = 0.88) -> dict[str, Any]:
        x, y = self.rng.randint(40, 280), self.rng.randint(40, 160)
        return {
            "camera_id": cam.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "anpr" if plate else "detection",
            "object_type": object_type,
            "local_track_id": f"t{self.tick}-{cam.id}",
            "plate_number": plate,
            "confidence": confidence,
            "attributes": attrs,
            "bbox": {"x": x, "y": y, "w": 90, "h": 50},
        }
