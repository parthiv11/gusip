from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.camera import Camera, Department
from app.schemas.common import GapZone

# Approximate urban cores used for coverage gap heuristics (PoC).
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


async def gap_analysis(db: AsyncSession) -> list[GapZone]:
    counts = (
        await db.execute(
            select(Camera.city, func.count(Camera.id)).where(Camera.is_active.is_(True)).group_by(Camera.city)
        )
    ).all()
    by_city = {c: n for c, n in counts}
    zones: list[GapZone] = []
    for city, (_lat, _lon, recommended) in CITY_CENTROIDS.items():
        n = by_city.get(city, 0)
        deficit = max(0, recommended - n)
        if deficit == 0 and n < recommended + 2:
            hint = "Core covered; arterial / outskirts still sparse"
            rec = 2
        elif n == 0:
            hint = "No federated cameras in this urban core"
            rec = recommended
        else:
            hint = f"{n} cameras vs indicative urban requirement of {recommended}+"
            rec = deficit or 1
        zones.append(GapZone(city=city, camera_count=n, uncovered_hint=hint, recommended_cameras=rec))
    return sorted(zones, key=lambda z: z.recommended_cameras, reverse=True)


async def nearby_cameras(db: AsyncSession, lon: float, lat: float, radius_m: float = 2000):
    sql = text(
        """
        SELECT id, code, name, city, status,
               ST_Distance(location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
        FROM cameras
        WHERE is_active
          AND ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)
        ORDER BY dist_m ASC
        LIMIT 25
        """
    )
    result = await db.execute(sql, {"lon": lon, "lat": lat, "radius": radius_m})
    return [dict(r._mapping) for r in result]
