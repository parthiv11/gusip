"""Seed departments, 50 cameras, users, and watchlist for the GUSIP PoC."""

from __future__ import annotations

import asyncio

from geoalchemy2.elements import WKTElement
from sqlalchemy import select, text

from app.core.plates import normalize_plate
from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models.camera import Camera, Department
from app.models.user import User
from app.models.watchlist import WatchlistEntry

DEPARTMENTS = [
    ("ACP", "Ahmedabad City Police"),
    ("SCP", "Surat City Police"),
    ("VCP", "Vadodara City Police"),
    ("RCP", "Rajkot City Police"),
    ("GCP", "Gandhinagar Police"),
    ("TRF", "Traffic Police Gujarat"),
    ("RTO", "RTO / Transport"),
    ("HWY", "Highway Police / GSRDC"),
    ("RPF", "Railway Protection Force"),
    ("CST", "Coastal Police"),
    ("BMC", "Municipal Corporation CCTV"),
    ("SENT", "Sentinel Evaluation Feeds (SCRB)"),
]

# (code, name, dept_code, city, lat, lon, type, source, vendor, ownership, connectivity)
CAMERAS: list[tuple] = [
    ("AMD-SG-01", "SG Highway Junction North", "TRF", "Ahmedabad", 23.0475, 72.5310, "ip", "rtsp", "Hikvision", "Traffic Police", "fiber"),
    ("AMD-SG-02", "SG Highway ISKCON", "TRF", "Ahmedabad", 23.0401, 72.5088, "ip", "onvif", "Dahua", "Traffic Police", "fiber"),
    ("AMD-CG-01", "CG Road Law Garden", "ACP", "Ahmedabad", 23.0276, 72.5580, "ip", "vendor_api", "Hikvision", "Ahmedabad City Police", "fiber"),
    ("AMD-AS-01", "Ashram Road Paldi", "ACP", "Ahmedabad", 23.0138, 72.5682, "ip", "rtsp", "CP Plus", "Ahmedabad City Police", "fiber"),
    ("AMD-NA-01", "Naroda Highway Toll", "HWY", "Ahmedabad", 23.0722, 72.6598, "ip", "onvif", "Hikvision", "Highway Police", "leased"),
    ("AMD-SK-01", "Sarkhej Circle", "TRF", "Ahmedabad", 22.9904, 72.5019, "ip", "rtsp", "Dahua", "Traffic Police", "fiber"),
    ("AMD-VS-01", "Vastrapur Lake East", "BMC", "Ahmedabad", 23.0387, 72.5294, "ip", "vendor_api", "UNV", "AMC", "fiber"),
    ("AMD-MN-01", "Maninagar Railway Overbridge", "RPF", "Ahmedabad", 22.9978, 72.6021, "analog", "onvif", "CP Plus", "Railway", "copper"),
    ("AMD-BA-01", "Bapunagar Crossroads", "ACP", "Ahmedabad", 23.0379, 72.6305, "ip", "rtsp", "Hikvision", "Ahmedabad City Police", "fiber"),
    ("AMD-TH-01", "Thaltej Shilaj Road", "ACP", "Ahmedabad", 23.0529, 72.4976, "ip", "onvif", "Dahua", "Ahmedabad City Police", "fiber"),
    ("AMD-NV-01", "Navrangpura University", "ACP", "Ahmedabad", 23.0365, 72.5468, "ip", "vendor_api", "Hikvision", "Ahmedabad City Police", "fiber"),
    ("AMD-GH-01", "Geeta Mandir Bus Port", "BMC", "Ahmedabad", 23.0156, 72.5889, "ip", "rtsp", "Hikvision", "AMC", "fiber"),
    ("AMD-AP-01", "Airport Approach Road", "ACP", "Ahmedabad", 23.0761, 72.6347, "ip", "onvif", "Axis", "Ahmedabad City Police", "fiber"),
    ("AMD-CT-01", "Kalupur Railway Station Forecourt", "RPF", "Ahmedabad", 23.0270, 72.6016, "ip", "vendor_api", "Hikvision", "Railway", "fiber"),
    ("AMD-SP-01", "SP Ring Road Nikol", "HWY", "Ahmedabad", 23.0550, 72.6640, "ip", "rtsp", "Dahua", "Highway Police", "leased"),
    ("AMD-OT-01", "Odhav GIDC Gate", "ACP", "Ahmedabad", 23.0220, 72.6712, "analog", "onvif", "CP Plus", "Ahmedabad City Police", "copper"),
    ("SRT-RD-01", "Ring Road Adajan", "SCP", "Surat", 21.1970, 72.7936, "ip", "rtsp", "Hikvision", "Surat City Police", "fiber"),
    ("SRT-VR-01", "Varachha Main Road", "SCP", "Surat", 21.2144, 72.8478, "ip", "onvif", "Dahua", "Surat City Police", "fiber"),
    ("SRT-AT-01", "Athwa Gate", "TRF", "Surat", 21.1705, 72.8012, "ip", "vendor_api", "Hikvision", "Traffic Police", "fiber"),
    ("SRT-CN-01", "Canal Road Vesu", "SCP", "Surat", 21.1418, 72.7704, "ip", "rtsp", "UNV", "Surat City Police", "fiber"),
    ("SRT-DT-01", "Dumas Beach Approach", "CST", "Surat", 21.0833, 72.7142, "ip", "onvif", "Hikvision", "Coastal Police", "wireless"),
    ("SRT-ST-01", "Surat Railway Station", "RPF", "Surat", 21.2050, 72.8405, "ip", "vendor_api", "Hikvision", "Railway", "fiber"),
    ("SRT-UC-01", "Udhna Chowk", "TRF", "Surat", 21.1662, 72.8411, "ip", "rtsp", "Dahua", "Traffic Police", "fiber"),
    ("SRT-KA-01", "Katargam Fire Station", "SCP", "Surat", 21.2298, 72.8270, "analog", "onvif", "CP Plus", "Surat City Police", "copper"),
    ("SRT-PI-01", "Piplod Star Bazaar", "BMC", "Surat", 21.1576, 72.7739, "ip", "rtsp", "Hikvision", "SMC", "fiber"),
    ("SRT-HW-01", "Sachin GIDC Highway", "HWY", "Surat", 21.0870, 72.8775, "ip", "onvif", "Dahua", "Highway Police", "leased"),
    ("VAD-RC-01", "Race Course Circle", "VCP", "Vadodara", 22.3102, 73.1731, "ip", "rtsp", "Hikvision", "Vadodara City Police", "fiber"),
    ("VAD-AK-01", "Akota Garden", "VCP", "Vadodara", 22.2938, 73.1654, "ip", "onvif", "Dahua", "Vadodara City Police", "fiber"),
    ("VAD-AL-01", "Alkapuri R.C. Dutt", "TRF", "Vadodara", 22.3139, 73.1758, "ip", "vendor_api", "Hikvision", "Traffic Police", "fiber"),
    ("VAD-ST-01", "Vadodara Junction", "RPF", "Vadodara", 22.3107, 73.1809, "ip", "rtsp", "Hikvision", "Railway", "fiber"),
    ("VAD-NH-01", "NH-48 Vasad Approach", "HWY", "Vadodara", 22.3301, 73.0788, "ip", "onvif", "Dahua", "Highway Police", "leased"),
    ("VAD-MC-01", "Makarpura GIDC", "BMC", "Vadodara", 22.2704, 73.1952, "analog", "vendor_api", "CP Plus", "VMC", "copper"),
    ("RJT-GN-01", "Race Course Gondal Road", "RCP", "Rajkot", 22.2916, 70.7930, "ip", "rtsp", "Hikvision", "Rajkot City Police", "fiber"),
    ("RJT-KL-01", "Kalawad Road", "RCP", "Rajkot", 22.2814, 70.7745, "ip", "onvif", "Dahua", "Rajkot City Police", "fiber"),
    ("RJT-TR-01", "Trikon Baug", "TRF", "Rajkot", 22.3039, 70.8022, "ip", "vendor_api", "Hikvision", "Traffic Police", "fiber"),
    ("RJT-ST-01", "Rajkot Railway Station", "RPF", "Rajkot", 22.3112, 70.8028, "ip", "rtsp", "Hikvision", "Railway", "fiber"),
    ("RJT-NH-01", "NH-27 Kotharia", "HWY", "Rajkot", 22.2488, 70.8011, "ip", "onvif", "Dahua", "Highway Police", "leased"),
    ("GNR-SC-01", "Sector 21 CH Road", "GCP", "Gandhinagar", 23.2234, 72.6467, "ip", "rtsp", "Hikvision", "Gandhinagar Police", "fiber"),
    ("GNR-IN-01", "Infocity Gate", "GCP", "Gandhinagar", 23.1965, 72.6338, "ip", "onvif", "Axis", "Gandhinagar Police", "fiber"),
    ("GNR-SG-01", "Akshardham Approach", "TRF", "Gandhinagar", 23.2394, 72.6772, "ip", "vendor_api", "Hikvision", "Traffic Police", "fiber"),
    ("GNR-HW-01", "AHMEDABAD-GNR SP Ring Link", "HWY", "Gandhinagar", 23.1688, 72.6120, "ip", "rtsp", "Dahua", "Highway Police", "leased"),
    ("BHV-CR-01", "Ghogha Circle", "TRF", "Bhavnagar", 21.7645, 72.1519, "ip", "onvif", "Hikvision", "Traffic Police", "fiber"),
    ("BHV-PT-01", "Bhavnagar Port Road", "CST", "Bhavnagar", 21.7502, 72.1901, "ip", "rtsp", "Dahua", "Coastal Police", "wireless"),
    ("JMN-DC-01", "Digvijay Plot", "TRF", "Jamnagar", 22.4707, 70.0577, "ip", "vendor_api", "Hikvision", "Traffic Police", "fiber"),
    ("JMN-PT-01", "Bedi Port Approach", "CST", "Jamnagar", 22.4799, 70.0531, "ip", "onvif", "Dahua", "Coastal Police", "wireless"),
    ("JND-MC-01", "Junagadh MG Road", "TRF", "Junagadh", 21.5222, 70.4579, "ip", "rtsp", "CP Plus", "Traffic Police", "fiber"),
    ("JND-GR-01", "Girnar Taleti Road", "BMC", "Junagadh", 21.5258, 70.4702, "analog", "onvif", "Hikvision", "Municipality", "copper"),
    ("BRH-NH-01", "NH-48 Bharuch Bypass", "HWY", "Bharuch", 21.7051, 72.9959, "ip", "rtsp", "Dahua", "Highway Police", "leased"),
    ("BRH-NT-01", "Narmada Bridge Approach", "HWY", "Bharuch", 21.6950, 72.9910, "ip", "onvif", "Hikvision", "Highway Police", "leased"),
    ("AND-UN-01", "Anand Town Hall", "TRF", "Anand", 22.5645, 72.9289, "ip", "vendor_api", "Hikvision", "Traffic Police", "fiber"),
]

WATCHLIST = [
    {
        "entity_type": "vehicle",
        "category": "stolen_vehicle",
        "plate_number": "GJ 01 ST 0001",
        "name": "White Toyota Fortuner",
        "description": "Stolen from Satellite, Ahmedabad. Last FIR 112/2026.",
        "appearance_notes": "white SUV roof carrier",
        "extra": {"color": "white", "vehicle_class": "suv", "sim_tag": "stolen-fortuner"},
        "priority": "critical",
    },
    {
        "entity_type": "vehicle",
        "category": "blacklisted_vehicle",
        "plate_number": "GJ 05 BL 9999",
        "name": "Black Honda City",
        "description": "Linked to hit-and-run, Surat Varachha.",
        "appearance_notes": "black sedan left dent",
        "extra": {"color": "black", "vehicle_class": "sedan", "sim_tag": "blacklist-city"},
        "priority": "high",
    },
    {
        "entity_type": "person",
        "category": "wanted_person",
        "plate_number": None,
        "name": "Rakesh M.",
        "description": "Wanted in NDPS case. Frequent SG Highway / Sarkhej.",
        "appearance_notes": "grey hoodie",
        "extra": {"sim_tag": "wanted-rakesh"},
        "priority": "critical",
    },
    {
        "entity_type": "person",
        "category": "missing_person",
        "plate_number": None,
        "name": "Anjali P.",
        "description": "Missing from Vadodara Alkapuri. Age 16. Non-criminal locating only.",
        "appearance_notes": "school bag blue",
        "extra": {"sim_tag": "missing-anjali"},
        "priority": "high",
    },
]

USERS = [
    ("admin", "GUSIP@admin2026", "Control Room Administrator", "admin@gusip.gujarat.gov.in", "system_admin", None),
    ("operator", "GUSIP@ops2026", "SOC Operator – Ahmedabad", "operator@gusip.gujarat.gov.in", "control_room_operator", "ACP"),
    ("investigator", "GUSIP@inv2026", "Investigation Officer", "io@gusip.gujarat.gov.in", "investigation_officer", "ACP"),
    ("coordinator", "GUSIP@coord2026", "Ahmedabad Department Coordinator", "coord@gusip.gujarat.gov.in", "department_coordinator", "ACP"),
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        dept_map: dict[str, Department] = {}
        rows = list((await db.execute(select(Department))).scalars())
        dept_map = {d.code: d for d in rows}
        for code, name in DEPARTMENTS:
            if code in dept_map:
                continue
            d = Department(code=code, name=name, zone="Gujarat")
            db.add(d)
            await db.flush()
            dept_map[code] = d

        cam_count = (await db.execute(select(Camera))).scalars().first()
        if not cam_count:
            for row in CAMERAS:
                code, name, dept, city, lat, lon, ctype, source, vendor, owner, conn = row
                db.add(
                    Camera(
                        code=code,
                        name=name,
                        department_id=dept_map[dept].id,
                        camera_type=ctype,
                        ownership=owner,
                        source_type=source,
                        vendor=vendor,
                        rtsp_url=f"rtsp://adapter.local/{code}" if source == "rtsp" else None,
                        onvif_endpoint=f"http://onvif.local/{code}/onvif/device_service" if source == "onvif" else None,
                        vendor_api_ref=f"{vendor}:{code}" if source == "vendor_api" else None,
                        status="online",
                        connectivity=conn,
                        storage_details="Edge NVR 7-day + source VMS (not centralised)",
                        amc_status="active",
                        coverage_radius_m=90 if ctype == "ip" else 50,
                        location=WKTElement(f"POINT({lon} {lat})", srid=4326),
                        latitude=lat,
                        longitude=lon,
                        city=city,
                        address=name,
                        extra={"codec": "h264", "fps": 15 if ctype == "analog" else 25, "resolution": "1080p" if ctype == "ip" else "d1"},
                    )
                )

        user_exists = (await db.execute(select(User))).scalars().first()
        if not user_exists:
            for username, password, full_name, email, role, dept_code in USERS:
                db.add(
                    User(
                        username=username,
                        full_name=full_name,
                        email=email,
                        hashed_password=hash_password(password),
                        role=role,
                        department_id=dept_map[dept_code].id if dept_code else None,
                        is_active=True,
                    )
                )

        wl_exists = (await db.execute(select(WatchlistEntry))).scalars().first()
        if not wl_exists:
            for item in WATCHLIST:
                db.add(
                    WatchlistEntry(
                        **item,
                        plate_normalized=normalize_plate(item["plate_number"]),
                        created_by="seed",
                        is_active=True,
                    )
                )

        await db.commit()
        print("GUSIP seed complete: departments, 50 cameras, users, watchlist.")


if __name__ == "__main__":
    asyncio.run(seed())
