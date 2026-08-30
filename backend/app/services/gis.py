from __future__ import annotations

import math

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera, Department
from app.schemas.common import GapZone

# Approximate urban cores used for coverage gap heuristics (PoC).
# Tuple is (lat, lon, recommended cameras in the 12 km urban core).
CITY_CENTROIDS = {
    "Ahmedabad": (23.0225, 72.5714, 12),
    "Surat": (21.1702, 72.8311, 10),
    "Vadodara": (22.3072, 73.1812, 8),
    "Rajkot": (22.3039, 70.8022, 7),
    "Gandhinagar": (23.2156, 72.6369, 5),
    "Bhavnagar": (21.7645, 72.1519, 4),
    "Jamnagar": (22.4707, 70.0577, 4),
    "Junagadh": (21.5222, 70.4579, 3),
    "Bharuch": (21.7051, 72.9959, 3),
    "Anand": (22.5645, 72.9289, 3),
}

CORE_RADIUS_M = 12_000


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlamb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlamb / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def city_coverage_gap(
    city: str,
    lat: float,
    lon: float,
    recommended: int,
    cameras: list[tuple[float, float]],
) -> GapZone:
    nearby = [(clat, clon) for clat, clon in cameras if haversine_m(lat, lon, clat, clon) <= CORE_RADIUS_M]
    n = len(nearby)
    deficit = max(0, recommended - n)
    if n == 0:
        hint = "No federated cameras in this urban core"
        rec = recommended
    else:
        mean_m = sum(haversine_m(lat, lon, clat, clon) for clat, clon in nearby) / n
        clustered = n >= 2 and mean_m < 2_500
        if clustered and deficit == 0:
            hint = f"{n} cameras clustered within {int(mean_m)} m of the core; arterial / outskirts still dark"
            rec = max(2, recommended // 2)
        elif clustered:
            hint = f"{n} cameras bunched downtown vs urban requirement of {recommended}+; next buy should be an arterial road"
            rec = deficit
        elif deficit == 0:
            hint = f"{n} cameras cover the core; keep one spare for outskirts"
            rec = 1
        else:
            hint = f"{n} cameras inside 12 km vs indicative urban requirement of {recommended}+"
            rec = deficit
    return GapZone(city=city, camera_count=n, uncovered_hint=hint, recommended_cameras=rec)


async def cameras_geojson(db: AsyncSession, department_id: int | None = None, status: str | None = None):
    q = select(Camera, Department).join(Department, Camera.department_id == Department.id).where(Camera.is_active.is_(True))
    if department_id:
        q = q.where(Camera.department_id == department_id)
    if status:
        q = q.where(Camera.status == status)
    rows = (await db.execute(q)).all()
    features = []
    for cam, dept in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [cam.longitude, cam.latitude]},
                "properties": {
                    "id": cam.id,
                    "code": cam.code,
                    "name": cam.name,
                    "status": cam.status,
                    "source_type": cam.source_type,
                    "camera_type": cam.camera_type,
                    "department": dept.name,
                    "department_code": dept.code,
                    "city": cam.city,
                    "coverage_radius_m": cam.coverage_radius_m,
                    "amc_status": cam.amc_status,
                    "vendor": cam.vendor,
                    "ownership": cam.ownership,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


async def gap_analysis(db: AsyncSession, department_id: int | None = None) -> list[GapZone]:
    q = select(Camera.latitude, Camera.longitude).where(Camera.is_active.is_(True))
    if department_id is not None:
        q = q.where(Camera.department_id == department_id)
    cameras = [(float(lat), float(lon)) for lat, lon in (await db.execute(q)).all() if lat is not None and lon is not None]
    zones = [
        city_coverage_gap(city, lat, lon, recommended, cameras)
        for city, (lat, lon, recommended) in CITY_CENTROIDS.items()
    ]
    return sorted(zones, key=lambda z: z.recommended_cameras, reverse=True)


async def nearby_cameras(
    db: AsyncSession,
    lon: float,
    lat: float,
    radius_m: float = 2000,
    department_id: int | None = None,
):
    sql = text(
        """
        SELECT id, code, name, city, status,
               ST_Distance(location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
        FROM cameras
        WHERE is_active
          AND (:department_id IS NULL OR department_id = :department_id)
          AND ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)
        ORDER BY dist_m ASC
        LIMIT 25
        """
    )
    result = await db.execute(
        sql,
        {"lon": lon, "lat": lat, "radius": radius_m, "department_id": department_id},
    )
    return [dict(r._mapping) for r in result]
