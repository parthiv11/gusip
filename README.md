# GUSIP — Gujarat Unified Surveillance Intelligence Platform

**Gujarat Police Innovation Challenge 2026**  
One wall for cameras that already exist. Video stays on the departmental NVR. Hits, stills, and the GIS line come here.

PoC: 50 own/demo cameras + 31 official Sentinel feeds · Scale path: 80,000+ without a statewide NVR

## Proposed solution

A stolen Fortuner leaves Paldi and is on the Gandhinagar link six minutes later. Today that is three control rooms and a WhatsApp still. GUSIP is the statewide **picture** of cameras that already exist — Traffic, commissionerate, AMC, highway, railway, and the official Sentinel wall. It is not a new NVR. Video stays on the box that already records it. We lift a still, a plate, a GPS pin, and an alert.

The operator’s wall defaults to government feeds (Chimanbhai Bridge is live from the Sentinel ingest catalogue). A watchlist hit jumps that camera into the large pane; repeats on the same camera become ×27, not 27 cards. Yellow numbered pins on the map are open alerts with the screenshot attached. Search will not run until the officer picks a purpose. An Ahmedabad coordinator only sees Ahmedabad until they type an FIR reason and take a time-boxed break-glass.

The PoC is 50 departmental-style cameras plus 31 official Sentinel cameras. Eighty thousand cameras later we still do not store eighty thousand movies in Gandhinagar — we store events, and we add GPUs where the adapters sit.

## Key features

- Gov-feeds tab plays official Sentinel cameras through our proxy (no VMS swap)
- Own/demo wall for RTSP / ONVIF / vendor-style cameras on the same event JSON
- Watchlist hit enlarges the camera; same plate on same camera stacks as ×N
- Yellow map badges = open alerts; click for plate, confidence, evidence still
- Stolen-corridor demo: GJ 01 ST 0001 across five junctions in under 8 seconds
- Investigate requires a purpose (stolen, wanted, evaluation…) and writes audit
- Four logins: operator cannot export; IO can; coordinator is home-district + break-glass
- GIS coverage gaps so the next camera is bought for a dark road, not a vendor quota

## Expected impact

- **Minutes to seconds:** Paldi → SG Highway → Gandhinagar is one GIS line, not three phone calls.
- **No second NVR bill:** 80,000 streams stay on departmental disk; GUSIP keeps stills and clips.
- **Honest government data:** jury feeds are in the product, not a slide screenshot.
- **Fewer fat-finger leaks:** no search without purpose; operators cannot download CSV.
- **One hall down ≠ state blind:** Surat NVR can die; Ahmedabad and Sentinel keep playing.
- **Where to spend:** gap list (Bhavnagar 2 cameras vs need 4+) instead of another city-centre VMS.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18 (Vite — not Next.js) |
| Backend | FastAPI |
| Database | PostgreSQL 16 + PostGIS, Redis |
| AI models | YOLOv8 (Ultralytics hook for GPU; PoC uses the same event contract in simulate mode), Tesseract OCR (ANPR on official Sentinel frames), ByteTrack-shaped multi-camera track IDs |
| APIs used | Gujarat Police Sentinel ingest catalogue (`GET /api/ingest` on `live.corp8.cloud` — RTSP TCP for AI, HLS if `:8554` is blocked, WHEP for browser preview), OpenStreetMap / Leaflet tiles (GIS, not Google Maps), GUSIP REST + WebSocket (`/api/v1`, `/ws/alerts`, `/ws/live`), RTSP / ONVIF / vendor-API adapter interfaces |
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

GUSIP onboarded the official wall via [GET /api/ingest](https://live.corp8.cloud/api/ingest) ([integrator contract](https://sentinel.gujarat.gov.in/resource), problem statements: [sentinel.gujarat.gov.in/problems](https://sentinel.gujarat.gov.in/problems)). Camera IDs and URLs come from that catalogue, not from hard-coded paths.

1. Open the control room → **Gov feeds**
2. Click **Sync Sentinel** (worker also syncs every 2 minutes)
3. Select a camera — the operator player uses the authenticated `/stream/<id>` range fallback. ANPR/YOLO consume catalogue RTSP over TCP (`rtsp_transport=tcp`); HLS only if port 8554 is blocked. Timing is PTS, not FPS.
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
k8s/         Kubernetes production pack (quota, HPA, TLS, NetworkPolicy)
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

Hackathon form URLs (public repo):

- Presentation PDF: https://github.com/parthiv11/gusip/raw/main/docs/submission/GUSIP-presentation.pdf
- Architecture SVG: https://github.com/parthiv11/gusip/raw/main/docs/submission/architecture.svg
- Workflow SVG: https://github.com/parthiv11/gusip/raw/main/docs/submission/workflow.svg
- Screenshots: https://github.com/parthiv11/gusip/tree/main/docs/submission/screenshots


## Acceptance mapped to this PoC

| Criterion | How to show it |
|---|---|
| Two source types | Camera registry badges: `rtsp`, `onvif`, `vendor_api`, `sentinel` |
| Government-provided feed | Control room → Gov feeds (Sentinel `/api/ingest` adapter) |
| Multi-camera vehicle tracking | Investigate → `GJ 01 ST 0001` GIS polyline |
| Watchlist alert & latency | Alert inbox; demo scenario prints hop times (target &lt; 8s) |
| Searchable history + GIS | Investigate + GIS pages |
| RBAC + audit | Four roles; Admin → Audit trail |
| Scale to 80k | [docs/scalability.md](docs/scalability.md) |

## Licence / use

Built for the Gujarat Police Innovation Challenge 2026. Intended for authorised law-enforcement evaluation only.
