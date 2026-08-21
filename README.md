# GUSIP — Gujarat Unified Surveillance Intelligence Platform

**Gujarat Police Innovation Challenge 2026**  
Hybrid architecture: Model 1 (registry/GIS) + Model 2 (unified viewing) + Model 3 (federation middleware)  
Not Model 4 — departmental VMS is not replaced. PoC: ~50 cameras · Scale path: 80,000+

## Proposed solution

GUSIP (Gujarat Unified Surveillance Intelligence Platform) is a hybrid overlay on the mandatory **Model 1** CCTV registry and GIS. It federates existing departmental VMS/NVR estates (**Model 3**) and gives one control-room picture with selective analytics (**Model 2**). It is not **Model 4**: departmental video systems stay in place as the system of record; GUSIP does not ingest 24×7 statewide video.

Adapters (RTSP, ONVIF, vendor API, and the official Sentinel evaluation feeds) normalise cameras into a PostGIS registry. Only **metadata, detections, short evidence clips, and alerts** move to the centre. A statewide event bus drives ANPR, watchlist matching, multi-camera tracks, and an audited Investigate search. Operators work a unified wall that auto-focuses on watchlist hits (manage-by-exception). Access is four visible roles with purpose-bound search, export controls, and time-boxed break-glass for other districts.

The PoC runs ~50 own/demo cameras plus 31 official government feeds, with a documented path to 80,000+ cameras by scaling adapters and regional AI, not by building a central NVR. Departmental VMS systems continue to operate independently (FR-2.5).

## Key features

- Statewide CCTV registry with GIS map, health, ownership, and coverage-gap analysis (Model 1)
- Federation adapters for RTSP, ONVIF, vendor APIs, and official Sentinel live feeds without replacing departmental VMS
- Unified control-room wall: government feeds, own/demo cameras, or both, with GIS overlay
- Alert-driven auto-focus: watchlist hit enlarges the camera, pages the wall, and coalesces repeat hits
- ANPR and multi-camera tracking (stolen / blacklisted vehicles, wanted / missing persons)
- Investigate search by plate, time, city, and attributes, with mandatory purpose and full audit
- Watchlist, case folders, and role-gated evidence export (CSV / case JSON)
- Four-role RBAC with department scope and time-boxed break-glass (reason + auto-expire)
- Operator watermark and immutable-style audit of view, search, export, and ack
- Same event contract for simulated PoC detections and future YOLO/ByteTrack workers

## Expected impact

- **Time-to-alert:** PoC path targets under 8 seconds from camera event to inbox (stolen-vehicle corridor demo).
- **Cross-district pursuit:** one GIS journey instead of phone hops between control rooms; coordinator break-glass unlocks other districts with an extra audit trail.
- **Cost vs Model 4:** avoid statewide 24×7 bitstream storage and WAN for ~80,000 streams; keep paying AMC on existing NVRs; centralise clips/snapshots only.
- **Coverage decisions:** GIS gap analysis so new cameras go where density is low, not where a vendor already sold a VMS.
- **Accountability:** every search states a purpose; operators cannot export; CSV/case export is investigator/coordinator/admin only.
- **Continuity:** one departmental VMS outage does not blank the state picture; source systems keep running independently.
- **Scale path:** 50-camera PoC on a small VM with no GPU; city pilot then regional GPU farms; event bus sized for ~16,000 filtered events/s at 80,000 cameras.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18 (Vite — not Next.js) |
| Backend | FastAPI |
| Database | PostgreSQL 16 + PostGIS, Redis |
| AI models | YOLOv8 (Ultralytics hook for GPU; PoC uses the same event contract in simulate mode), Tesseract OCR (ANPR on official Sentinel frames), ByteTrack-shaped multi-camera track IDs |
| APIs used | Gujarat Police Sentinel Live-Feed API (`live.sentinelgujarat.in` — catalog, state, stream), OpenStreetMap / Leaflet tiles (GIS, not Google Maps), GUSIP REST + WebSocket (`/api/v1`, `/ws/alerts`, `/ws/live`), RTSP / ONVIF / vendor-API adapter interfaces |
| Cloud platform | On-premise (Docker Compose PoC; Kubernetes manifests in-repo; MinIO as S3-compatible object store) |
| Programming languages | Python, TypeScript, SQL, JavaScript |
| Frameworks | FastAPI, React 18, SQLAlchemy, GeoAlchemy2, Leaflet / react-leaflet, Tailwind CSS, Ultralytics YOLO (optional GPU path) |
| Other tools | Docker, Docker Compose, Kubernetes, Git, MinIO, Nginx, ffmpeg, pytest, Vite, Tesseract, Redis, PostgreSQL/PostGIS |

## Quick start

```bash
cd gusip
docker compose up -d --build
# wait until backend is healthy, then open:
# http://localhost:8080
```

| User | Password | Role |
|---|---|---|
| `operator` | `GUSIP@ops2026` | Control Room Operator |
| `investigator` | `GUSIP@inv2026` | Investigation Officer |
| `coordinator` | `GUSIP@coord2026` | Department Coordinator (Ahmedabad) |
| `admin` | `GUSIP@admin2026` | System Administrator |

Demo watchlist plates:

- Stolen SUV: **GJ 01 ST 0001** (Ahmedabad SG Highway → Gandhinagar)
- Blacklisted sedan: **GJ 05 BL 9999** (Surat)

Force the stolen-vehicle corridor (live demo):

```bash
docker compose exec worker python -m app.workers.demo_scenario
```

Then search that plate on **Investigate**.

### Government evaluation feeds (mandatory)

GUSIP onboarded the official wall at [live.sentinelgujarat.in](https://live.sentinelgujarat.in/) (problem statements: [sentinel.gujarat.gov.in/problems](https://sentinel.gujarat.gov.in/problems)).

1. Open the control room → **Gov feeds**
2. Click **Sync Sentinel** (worker also syncs every 2 minutes)
3. Select a camera — live progressive stream plays through the GUSIP adapter (`/api/v1/feeds/sentinel/{id}/stream`)
4. Add the jury-issued plate on **Watchlist**
5. Wait for sequential ANPR sampling (ffmpeg + Tesseract, one camera at a time)
6. Download **Investigate → ANPR report (CSV)** for the submission output report

Own/demo wall remains available for the participant-feed video.

API: `http://localhost:8000/docs` · Health: `http://localhost:8000/health`

## Repository layout

```
backend/     FastAPI intelligence + adapter workers
frontend/    React control-room console
docs/        HLD, architecture, API, deploy, security, scale, cost
k8s/         Kubernetes manifests for the same topology
```

## PoC vs production inference

Default `INFERENCE_MODE=simulate` generates realistic multi-source detections (own RTSP-style + government ONVIF + vendor API) so the demo works without GPUs or live government streams.

Set `INFERENCE_MODE=yolo` on GPU nodes and install `ultralytics` to switch the same pipeline to YOLOv8 + ByteTrack. The event contract does not change.

## Documentation

| Document | Path |
|---|---|
| High-level design | [docs/HLD.md](docs/HLD.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| API | [docs/api.md](docs/api.md) |
| Deployment | [docs/deployment.md](docs/deployment.md) |
| Security | [docs/security.md](docs/security.md) |
| Scalability & sizing | [docs/scalability.md](docs/scalability.md) |
| Cost-benefit | [docs/cost-benefit.md](docs/cost-benefit.md) |
| SRS | [docs/SRS.md](docs/SRS.md) |
| **Submission pack** (presentation, HLD, diagrams) | [docs/submission/README.md](docs/submission/README.md) |

## Acceptance mapped to this PoC

| Criterion | How to show it |
|---|---|
| Two source types | Camera registry badges: `rtsp`, `onvif`, `vendor_api`, `sentinel` |
| Government-provided feed | Control room → Gov feeds (live.sentinelgujarat.in adapter) |
| Multi-camera vehicle tracking | Investigate → `GJ 01 ST 0001` GIS polyline |
| Watchlist alert & latency | Alert inbox; demo scenario prints hop times (target &lt; 8s) |
| Searchable history + GIS | Investigate + GIS pages |
| RBAC + audit | Four roles; Admin → Audit trail |
| Scale to 80k | [docs/scalability.md](docs/scalability.md) |

## Licence / use

Built for the Gujarat Police Innovation Challenge 2026. Intended for authorised law-enforcement evaluation only.
