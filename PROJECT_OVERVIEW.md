# GUSIP — Gujarat Unified Surveillance Intelligence Platform
## Comprehensive Project Overview

> **Hackathon:** Gujarat Police Innovation Challenge 2026  
> **Goal:** A statewide "one wall" for cameras that already exist — video stays on the departmental NVR; only intelligence (events, stills, plates, GIS data) flows to the centre.

---

## Table of Contents

1. [What is GUSIP?](#1-what-is-gusip)
2. [The Core Problem It Solves](#2-the-core-problem-it-solves)
3. [Key Features](#3-key-features)
4. [Architecture Overview](#4-architecture-overview)
5. [Repository Structure](#5-repository-structure)
6. [Backend — Deep Dive](#6-backend--deep-dive)
7. [Frontend — Deep Dive](#7-frontend--deep-dive)
8. [Data Flow: From Camera to Alert](#8-data-flow-from-camera-to-alert)
9. [Tech Stack](#9-tech-stack)
10. [Infrastructure & Deployment](#10-infrastructure--deployment)
11. [User Roles & Permissions](#11-user-roles--permissions)
12. [Demo Credentials & Test Data](#12-demo-credentials--test-data)
13. [Environment Configuration](#13-environment-configuration)
14. [Known Issues & Current State](#14-known-issues--current-state)
15. [Scale Path (PoC → 80,000 Cameras)](#15-scale-path-poc--80000-cameras)

---

## 1. What is GUSIP?

GUSIP (**Gujarat Unified Surveillance Intelligence Platform**) is a **federated surveillance intelligence system** built for the Gujarat Police. It is **not** a replacement NVR or VMS. Instead, it acts as a **smart aggregation and intelligence layer** on top of the cameras and recorders that already exist across police, traffic, municipal, highway, and railway departments.

Think of it as a **statewide operations picture** — it shows what cameras exist, where they are, what they are seeing (via sampled stills/events), and raises an alert the moment a watchlisted vehicle or person appears anywhere in Gujarat.

**PoC Scope:**
- 50 departmental/demo cameras simulated
- 31 official Gujarat Sentinel government feeds
- 10 cities, 11 departments
- Alert latency target: **< 8 seconds** from camera to operator inbox

---

## 2. The Core Problem It Solves

| Today (Without GUSIP) | With GUSIP |
|---|---|
| A stolen Fortuner spotted at Paldi needs 3 separate control room calls + WhatsApp stills to track it to Gandhinagar | One GIS polyline shows the entire route across all junctions in seconds |
| No single picture of how many cameras exist, where they are, or which are offline | Camera registry with PostGIS, live health status, coverage gap analysis |
| An officer can search any plate at any time — no audit trail | Search requires a **declared purpose**; every query is audit-logged |
| 27 separate alert cards for the same plate on the same camera | Smart coalescing: same plate on same camera = **×27 hit counter**, one card |
| Swapping VMS = expensive statewide project | Adapters are read-only; existing VMS/NVR are untouched |

---

## 3. Key Features

| Feature | Details |
|---|---|
| **Gov Feeds Tab** | Plays official Sentinel cameras from `live.sentinelgujarat.in` through a proxy — no VMS swap needed |
| **Own/Demo Wall** | RTSP / ONVIF / vendor-API cameras on the same event contract as Sentinel |
| **Watchlist Engine** | Exact + partial plate matching, appearance-based person matching |
| **Alert Coalescing** | Same plate on same camera stacks as ×N, not N separate cards |
| **GIS Map** | Yellow numbered pins = open alerts with screenshot; PostGIS spatial queries |
| **Coverage Gap Analysis** | Shows which cities are under-served so next camera budget is spent on dark roads, not duplicate city-centre cameras |
| **Investigation (Break-glass)** | Search requires a purpose (stolen, wanted, evaluation…); coordinators are home-district scoped and need a time-boxed break-glass to see other districts |
| **ANPR** | Automatic Number Plate Recognition via ffmpeg + Tesseract on Sentinel frames |
| **Multi-camera Tracking** | ByteTrack-style global track IDs link a vehicle across cameras |
| **Audit Trail** | Every login, search, and acknowledgement is logged |
| **Stolen-vehicle Demo** | GJ 01 ST 0001 across 5 junctions — GIS polyline in < 8 seconds |

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     OPERATOR BROWSER                        │
│              React 18 + Vite (port 5173 dev /               │
│                        port 8080 via Nginx)                 │
└────────────────────────┬────────────────────────────────────┘
                         │  REST /api/v1  +  WebSocket /ws
┌────────────────────────▼────────────────────────────────────┐
│              FastAPI Backend  (port 8000)                   │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────────┐  │
│  │   Auth   │ │ Cameras  │ │ Alerts  │ │  Search / GIS  │  │
│  │  (RBAC)  │ │  + Feeds │ │Watchlist│ │  Cases/Evidence│  │
│  └──────────┘ └──────────┘ └─────────┘ └────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Core Services                             │   │
│  │  Pipeline → Matching → Event Bus → WebSocket Relay  │   │
│  └──────────────────────────────────────────────────────┘   │
└──────┬──────────────┬──────────────────────────────┬────────┘
       │              │                              │
┌──────▼─────┐ ┌──────▼──────┐            ┌─────────▼───────┐
│ PostgreSQL │ │   Redis 7   │            │  MinIO (Object  │
│ 16+PostGIS │ │  (Pub/Sub + │            │  Store for      │
│            │ │   Live TTL) │            │  snapshots &    │
└────────────┘ └─────────────┘            │  evidence clips)│
                                          └─────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Worker Process                           │
│  Simulator (50 cams) | Sentinel ANPR | Inference | Demo     │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────▼──────────────────┐
              │   Gujarat Sentinel               │
              │   live.sentinelgujarat.in        │
              │   (Official gov CCTV feeds)      │
              └──────────────────────────────────┘
```

### Design Principles

1. **Centralise intelligence, not video** — only events, stills, embeddings, and short clips move to the centre.
2. **Federation before replacement** — RTSP, ONVIF Profile S/T, and vendor SDKs coexist.
3. **Zero-trust internally** — every API hop is authenticated; every query is audit-logged.
4. **Horizontal workers** — ingestion, inference, tracking, and matching scale independently.
5. **Do not break source operations** — adapters are read-only; departmental VMS remain the system of record.

---

## 5. Repository Structure

```
gusip/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── api/                # HTTP route handlers (14 route files)
│   │   │   ├── auth.py         # Login, tokens, break-glass
│   │   │   ├── cameras.py      # Camera registry CRUD + health
│   │   │   ├── alerts.py       # Alert inbox, acknowledge, dismiss
│   │   │   ├── watchlist.py    # Watchlist CRUD
│   │   │   ├── search.py       # Investigation search (purpose-gated)
│   │   │   ├── gis.py          # GeoJSON, gap analysis, nearby cameras
│   │   │   ├── cases.py        # Case folders + evidence
│   │   │   ├── evidence.py     # Evidence clip/snapshot endpoints
│   │   │   ├── feeds.py        # Sentinel sync + gov feed management
│   │   │   ├── admin.py        # Stats, audit trail
│   │   │   ├── integrations.py # VAHAN/SARTHI/eGujCop stubs
│   │   │   ├── ingest.py       # External detection ingest endpoint
│   │   │   └── ws.py           # WebSocket (/ws/alerts + /ws/live)
│   │   ├── core/               # Cross-cutting concerns
│   │   │   ├── audit.py        # Audit log writer
│   │   │   ├── break_glass.py  # Time-boxed cross-district access
│   │   │   ├── crypto.py       # Evidence encryption helpers
│   │   │   ├── plates.py       # Indian plate normalisation
│   │   │   ├── policy.py       # RBAC capabilities map
│   │   │   └── security.py     # JWT creation/verification
│   │   ├── models/             # SQLAlchemy ORM models
│   │   │   ├── camera.py       # Department + Camera
│   │   │   ├── event.py        # DetectionEvent + TrackPoint + Alert
│   │   │   ├── watchlist.py    # WatchlistEntry
│   │   │   ├── user.py         # User
│   │   │   ├── case.py         # Case + CaseEvent
│   │   │   └── audit.py        # AuditLog
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic
│   │   │   ├── pipeline.py     # Detection ingest pipeline (core loop)
│   │   │   ├── matching.py     # Watchlist hit + alert coalescing
│   │   │   ├── tracking.py     # Global track ID resolution
│   │   │   ├── gis.py          # GeoJSON + gap analysis queries
│   │   │   ├── anpr.py         # Tesseract ANPR wrapper
│   │   │   ├── event_bus.py    # Redis pub/sub wrapper
│   │   │   └── storage.py      # MinIO + placeholder snapshot gen
│   │   ├── workers/            # Background processes
│   │   │   ├── main.py         # Worker entry point
│   │   │   ├── simulator.py    # 50-camera simulated detection stream
│   │   │   ├── sentinel.py     # Sentinel ANPR + sync worker
│   │   │   ├── inference.py    # YOLO inference wrapper
│   │   │   ├── adapters.py     # RTSP/ONVIF adapter stubs
│   │   │   ├── demo_scenario.py# Stolen-vehicle corridor demo
│   │   │   └── sentinel_geo.py # Sentinel geographic data
│   │   ├── config.py           # Pydantic settings (env-vars)
│   │   ├── db.py               # Async SQLAlchemy engine setup
│   │   ├── main.py             # FastAPI app + lifespan
│   │   └── seed.py             # DB seeding (users, cameras, watchlist)
│   ├── tests/                  # pytest tests
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                   # React 18 + Vite + TypeScript
│   ├── src/
│   │   ├── api/                # API client helpers
│   │   ├── components/
│   │   │   ├── Shell.tsx       # App shell + sidebar navigation
│   │   │   ├── CameraTile.tsx  # Camera grid thumbnail
│   │   │   ├── FocusPlayer.tsx # Large focused camera player
│   │   │   ├── GovPlayer.tsx   # HLS/HTTP gov feed player
│   │   │   └── GujaratMap.tsx  # Leaflet map with camera pins + alert badges
│   │   ├── pages/
│   │   │   ├── ControlRoom.tsx # Main wall (cameras + alerts + mini-map)
│   │   │   ├── SearchPage.tsx  # Purpose-gated investigation search
│   │   │   ├── MapPage.tsx     # Full GIS map + gap analysis
│   │   │   ├── AlertsPage.tsx  # Alert inbox (full page)
│   │   │   ├── CamerasPage.tsx # Camera registry table
│   │   │   ├── WatchlistPage.tsx # Watchlist management
│   │   │   ├── CasesPage.tsx   # Case folders
│   │   │   ├── AdminPage.tsx   # Stats + audit trail
│   │   │   └── Login.tsx       # Login form
│   │   ├── types.ts            # TypeScript interfaces
│   │   ├── App.tsx             # Router setup
│   │   └── main.tsx            # React entry point
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── vite.config.ts
│   └── package.json
│
├── docs/                       # Technical documentation
│   ├── HLD.md                  # High-Level Design
│   ├── architecture.md
│   ├── api.md
│   ├── deployment.md
│   ├── security.md
│   ├── scalability.md
│   ├── cost-benefit.md
│   ├── SRS.md
│   └── submission/             # Hackathon submission assets
│
├── k8s/                        # Kubernetes manifests
│   ├── namespace.yaml
│   ├── apps.yaml               # Deployments + Services + Ingress
│   └── data.yaml               # StatefulSets for PG/Redis/MinIO
│
├── docker-compose.yml          # Full local stack
├── Makefile
└── .env.example
```

---

## 6. Backend — Deep Dive

### 6.1 Data Models

#### `Camera` (`backend/app/models/camera.py`)

| Field | Type | Description |
|---|---|---|
| `code` | String(64) | Unique camera ID (e.g., `AHM-RTSP-001`) |
| `source_type` | String(32) | `rtsp` / `onvif` / `vendor_api` / `sentinel` |
| `ownership` | String(64) | Owning department |
| `location` | Geography(POINT) | PostGIS spatial point |
| `latitude`, `longitude` | Float | Duplicated for quick access |
| `coverage_radius_m` | Float | Used in gap analysis (default 80 m) |
| `status` | String(32) | `online` / `offline` / `fault` |

#### `DetectionEvent` (`backend/app/models/event.py`)

Every inference detection is stored here:

| Field | Description |
|---|---|
| `plate_number` | Raw OCR plate (formatted) |
| `plate_normalized` | Canonical form for matching — `GJ01ST0001` |
| `global_track_id` | UUID linking sightings across cameras |
| `confidence` | 0.0 – 1.0 |
| `snapshot_url` | Path/URL to still image in MinIO |
| `embedding` | JSONB vector for appearance re-ID |
| `attributes` | JSONB (colour, make, clothing, etc.) |

#### `TrackPoint` (`backend/app/models/event.py`)

A geographic breadcrumb per detection — lat/lon + timestamp. Used to build the GIS polyline for multi-camera vehicle tracking.

#### `Alert` (`backend/app/models/event.py`)

Created when a `DetectionEvent` matches a `WatchlistEntry`:

| Field | Description |
|---|---|
| `status` | `new` / `acknowledged` / `dismissed` / `coalesced` |
| `payload` | JSONB — hit_count, fingerprint, city, lat/lon |
| `snapshot_url` | Evidence still |

**Key DB Constraint:** `UNIQUE INDEX ON alerts (watchlist_id, camera_id) WHERE status = 'new'`
→ At most one open alert card per camera+watchlist combination — enforced at the database level.

#### `WatchlistEntry` (`backend/app/models/watchlist.py`)

| Field | Description |
|---|---|
| `entity_type` | `vehicle` / `person` |
| `category` | `stolen_vehicle`, `wanted_person`, `blacklisted`, etc. |
| `plate_normalized` | Canonical plate for matching |
| `appearance_notes` | Text for person matching |
| `priority` | `critical` / `high` / `medium` / `low` |

#### `User` (`backend/app/models/user.py`)

| Field | Description |
|---|---|
| `role` | `control_room_operator` / `investigation_officer` / `department_coordinator` / `admin` |
| `department_id` | FK → scopes coordinator's view |

---

### 6.2 API Routes (all under `/api/v1`)

| Prefix | File | Purpose |
|---|---|---|
| `/auth` | `auth.py` | Login (OAuth2), `/me`, break-glass grant/revoke, create user |
| `/cameras` | `cameras.py` | Camera registry CRUD + health updates |
| `/watchlist` | `watchlist.py` | Watchlist CRUD |
| `/alerts` | `alerts.py` | List alerts, acknowledge, dismiss |
| `/search` | `search.py` | Purpose-gated search + ANPR CSV export |
| `/gis` | `gis.py` | GeoJSON, gap analysis, nearby cameras |
| `/cases` | `cases.py` | Case folders CRUD |
| `/evidence` | `evidence.py` | Serve snapshots/clips from MinIO |
| `/feeds` | `feeds.py` | Sentinel sync + gov feed listing |
| `/admin` | `admin.py` | Stats dashboard, audit log |
| `/integrations` | `integrations.py` | VAHAN/SARTHI/eGujCop stubs |
| `/ingest` | `ingest.py` | External detection push |
| `/ws/alerts` | `ws.py` | WebSocket — real-time alert stream |
| `/ws/live` | `ws.py` | WebSocket — real-time detection stream |

Interactive API docs at `http://localhost:8000/docs`.

---

### 6.3 Core Services

#### `pipeline.py` — The Central Detection Loop

```
ingest_detection(payload)
  1. Look up Camera by camera_id
  2. Normalise plate (Indian format → GJ01ST0001)
  3. resolve_global_track() → UUID across cameras
  4. Generate placeholder snapshot (MinIO)
  5. Write DetectionEvent to PostgreSQL
  6. Write TrackPoint (lat/lon breadcrumb)
  7. Update camera.last_seen_at
  8. load_active_watchlist()
  9. maybe_raise_alert() → check watchlist hit
 10. bus.publish_event() → Redis → WebSocket relay
```

#### `matching.py` — Watchlist Hit Engine

```python
match_entry(entry, plate_norm, attrs):
  # Vehicle exact plate match  → 97% confidence
  # Vehicle partial (last 4 + prefix) → 78% confidence
  # Person appearance notes in clothing → 72%
  # Person simulation tag match → 88%

maybe_raise_alert(db, event, camera, watchlist):
  # 1. Find best matching watchlist entry
  # 2. Check for existing open alert (same watchlist_id + camera_id)
  # 3a. Exists  → bump hit_count + update timestamp (coalesce)
  # 3b. Missing → create new Alert row
  # 4. Handle race condition with IntegrityError retry
  # 5. Publish to Redis → WebSocket
```

#### `tracking.py` — Global Track ID

Assigns a persistent `global_track_id` UUID across cameras using:
- Exact plate match within a time window
- Appearance embedding similarity for persons
- Falls back to new UUID if no match found

#### `gis.py` — Spatial Intelligence

- `cameras_geojson()` → GeoJSON FeatureCollection for Leaflet
- `gap_analysis()` → Compares camera count per city vs. minimum requirements → ranked deficit list
- `nearby_cameras()` → PostGIS `ST_DWithin` radius query

#### `event_bus.py` — Redis Pub/Sub Wrapper

- `publish_alert(payload)` → `gusip:alerts` channel
- `publish_event(payload)` → `gusip:live` channel
- `set_json(key, value, ttl=20)` → live detection cache per camera (20s TTL)

#### `storage.py` — Evidence in MinIO

- `save_snapshot_png(bytes, prefix)` → stores in `gusip-evidence` bucket, returns URL
- `generate_placeholder_snapshot(type, plate, code)` → generates labelled PNG for PoC mode

#### `anpr.py` — Plate Recognition

Wraps Tesseract OCR — pre-processes frames (grayscale/threshold), runs OCR in a thread pool, returns cleaned plate text.

---

### 6.4 Workers (`backend/app/workers/`)

| Worker | Description |
|---|---|
| `simulator.py` | Emits realistic detection events for 50 simulated cameras across 10 cities with varied plates/vehicles |
| `sentinel.py` | Syncs camera catalogue from `live.sentinelgujarat.in`; runs ANPR on Sentinel frame URLs via ffmpeg + Tesseract |
| `inference.py` | YOLO inference wrapper — passthrough in `simulate` mode; real YOLOv8+ByteTrack in `yolo` mode |
| `adapters.py` | RTSP/ONVIF adapter stubs — interfaces reserved for real camera integration |
| `demo_scenario.py` | Fires the stolen-vehicle corridor demo (GJ 01 ST 0001 across 5 junctions) |

---

### 6.5 Security & RBAC

#### Roles & Capabilities

| Role | View Cameras | Search (with purpose) | Export CSV | Add Watchlist | Admin Panel |
|---|---|---|---|---|---|
| `control_room_operator` | Own dept only | ❌ | ❌ | ❌ | ❌ |
| `investigation_officer` | All | ✅ | ✅ | ✅ | ❌ |
| `department_coordinator` | Home district* | ✅ | ✅ | ✅ | ❌ |
| `admin` | All | ✅ | ✅ | ✅ | ✅ |

*\* Break-glass allows temporary cross-district access with mandatory reason + audit log.*

#### Break-Glass Flow

1. Coordinator POSTs `/auth/break-glass` with `reason` + `duration_minutes`
2. Time-boxed grant stored in Redis
3. Every query during that window is flagged in audit log
4. Auto-expires; can be manually revoked

#### JWT Authentication

- Login → `POST /api/v1/auth/token` → JWT (`sub`, `role`, `dept` claims, HS256)
- All protected routes → `Depends(get_current_user)` → validates JWT → injects `User`
- Token lifetime: 480 minutes (8 hours)

#### Plate Normalisation

All Indian plate formats (`GJ 01 ST 0001`, `GJ-01-ST-0001`, `gj01st0001`) are canonicalised to `GJ01ST0001` before matching — prevents false negatives from format differences.

---

## 7. Frontend — Deep Dive

React 18 + TypeScript + Vite + Tailwind CSS. Dev port 5173; production port 8080 (Nginx).

### 7.1 Pages

#### `ControlRoom.tsx` — Main Wall (most complex page)
Layout: **8-column camera wall + 4-column alert inbox**

- **Wall tabs:** Gov feeds (Sentinel) / Own-demo / All
- **Camera grid:** 8 tiles per page with pagination
- **Focus player:** Large top pane showing selected camera + active alert overlay
- **Mini-map:** Gujarat map with alert pins
- **Alert inbox:** Right sidebar — coalesced alerts, hit counts, snapshot, acknowledge button
- **Alert sound:** Web Audio API oscillator on new critical/high priority alerts
- **Auto-focus:** On WebSocket alert, camera automatically jumps to large pane

#### `SearchPage.tsx` — Investigation (Purpose-Gated)
Must select purpose before searching. Returns timeline + GIS polyline + CSV export.

#### `MapPage.tsx` — Full GIS View
Full-screen Leaflet map with camera pins (colour by source type + status), open alert badges (yellow numbered), and gap analysis table.

#### `AlertsPage.tsx` / `CamerasPage.tsx` / `WatchlistPage.tsx` / `CasesPage.tsx`
Standard CRUD and list pages for their respective resources.

#### `AdminPage.tsx`
Stats dashboard + audit trail table. Admin-only.

---

### 7.2 Components

| Component | Purpose |
|---|---|
| `Shell.tsx` | Navigation sidebar with role-aware menu items; break-glass status indicator |
| `CameraTile.tsx` | Thumbnail card — red border on active alert; live detection overlay from WebSocket |
| `FocusPlayer.tsx` | Large camera pane — renders `GovPlayer` for Sentinel, placeholder for demo |
| `GovPlayer.tsx` | HLS (hls.js) video player with HTTP fallback for Sentinel feeds |
| `GujaratMap.tsx` | Leaflet map — camera markers + numbered alert badges; click to focus |

---

### 7.3 Real-time WebSocket Flow

```
Redis (gusip:alerts channel)
    ↓
ws.py relay_redis() background task
    ↓
Browser WebSocket /ws/alerts
    ↓
ControlRoom.tsx onmessage:
  1. Parse { type: "alert", data: {...} }
  2. coalesceInbox() — deduplicate by fingerprint (watchlist_id:camera_id)
  3. setAlerts() — re-render inbox
  4. focusAlert() — jump camera to focus pane
  5. playAlertTone() — audio beep for critical/high
```

Two channels:
- `/ws/alerts` — watchlist hits (triggers alarm + auto-focus)
- `/ws/live` — all detections (updates camera tile overlays)

---

## 8. Data Flow: From Camera to Alert

```
[Camera / Simulator / Sentinel Worker]
  Emits frame or detection event
        ↓
[Worker: inference.py / simulator.py / sentinel.py]
  YOLO detection or simulation
  Calls pipeline.ingest_detection(payload)
        ↓
[Service: pipeline.py]
  1. Normalise plate
  2. Resolve global track ID
  3. Generate snapshot → MinIO
  4. Write DetectionEvent to PostgreSQL
  5. Write TrackPoint (lat/lon)
  6. Call maybe_raise_alert()
        ↓
[Service: matching.py]
  1. Load active watchlist
  2. Find best match entry
  3a. Existing open alert → bump hit_count (coalesce)
  3b. No open alert → create new Alert row
  4. Publish to Redis
        ↓
[event_bus.py → Redis → ws.py relay]
        ↓
[Browser WebSocket → ControlRoom.tsx]
  Alert card appears
  Camera auto-focuses to large pane
  Audio beep plays
        ↓
[Operator acknowledges]
  POST /api/v1/alerts/:id/ack
  Audit log written
  status = "acknowledged"
```

**Target latency: < 8 seconds from camera frame to operator inbox.**

---

## 9. Tech Stack

### Backend Python Dependencies

| Library | Version | Purpose |
|---|---|---|
| fastapi | 0.115.6 | Web framework |
| uvicorn | 0.34.0 | ASGI server |
| sqlalchemy[asyncio] | 2.0.36 | Async ORM |
| asyncpg | 0.30.0 | PostgreSQL async driver |
| geoalchemy2 | 0.16.0 | PostGIS spatial types |
| pydantic + pydantic-settings | 2.10.4 / 2.7.0 | Validation + config |
| python-jose + passlib/bcrypt | - | JWT + password hashing |
| redis | 5.2.1 | Pub/sub + cache |
| httpx | 0.28.1 | Async HTTP client |
| minio | 7.2.12 | Object store client |
| ultralytics | 8.3.70 | YOLOv8 (GPU path) |
| pytesseract | 0.3.13 | ANPR (OCR) |
| shapely | 2.0.6 | GIS geometry ops |
| orjson | 3.10.12 | Fast JSON |

### Frontend Dependencies

| Library | Version | Purpose |
|---|---|---|
| react | 18.3.1 | UI framework |
| typescript | 5.7.2 | Type safety |
| vite | 6.0.6 | Build tool |
| react-router-dom | 6.28.1 | SPA routing |
| react-leaflet | 4.2.1 | Interactive map |
| hls.js | 1.5.20 | HLS video playback |
| lucide-react | 0.469.0 | Icons |
| tailwindcss | 3.4.17 | Utility CSS |

### Infrastructure

| Component | Technology |
|---|---|
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Cache & Bus | Redis 7 Alpine |
| Object Store | MinIO (S3-compatible) |
| Message Broker (optional) | Redpanda (Kafka-compatible) |
| Containers | Docker + Docker Compose |
| Kubernetes | K8s manifests included |
| Reverse Proxy | Nginx |

---

## 10. Infrastructure & Deployment

### Docker Compose Services

| Service | Image | Port | Role |
|---|---|---|---|
| `postgres` | postgis/postgis:16-3.4 | 5432 | Primary database + PostGIS |
| `redis` | redis:7-alpine | 6379 | Pub/sub bus + live cache |
| `minio` | minio/minio:latest | 9000 / 9001 | Object store |
| `redpanda` | redpanda:v24.2.9 | 19092 | Kafka broker (profile: `full`) |
| `backend` | gusip-backend:poc | 8000 | FastAPI API |
| `worker` | gusip-backend:poc | — | Background inference |
| `frontend` | gusip-frontend:poc | 8080 | Nginx + React app |

**Startup order:**
```
postgres (healthy) ──┐
redis (healthy) ─────┤──→ backend (seed DB + API) ──→ worker
minio ────────────────┘                               frontend
```

### Quick Start

```bash
cd gusip
docker compose up -d --build
# Wait ~60 seconds for all health checks to pass
# App:      http://localhost:8080
# API docs: http://localhost:8000/docs
# Health:   http://localhost:8000/health
```

### Kubernetes

`k8s/` contains production-ready manifests:
- `namespace.yaml` — Creates `gusip` namespace
- `apps.yaml` — Deployments (backend ×2, worker ×2, frontend ×2) + Services + Ingress
- `data.yaml` — StatefulSets for PostgreSQL, Redis, MinIO with PVC

---

## 11. User Roles & Permissions

| Role | Username | Password | Scope |
|---|---|---|---|
| Control Room Operator | `operator` | `GUSIP@ops2026` | Own department cameras; no search/export |
| Investigation Officer | `investigator` | `GUSIP@inv2026` | All cameras; purpose-gated search; CSV export |
| Department Coordinator | `coordinator` | `GUSIP@coord2026` | Home district (Ahmedabad); break-glass for others |
| System Admin | `admin` | `GUSIP@admin2026` | Full access; user management; audit trail |

---

## 12. Demo Credentials & Test Data

### Watchlist Plates

| Plate | Scenario | Route |
|---|---|---|
| `GJ 01 ST 0001` | Stolen SUV | Ahmedabad Paldi → SG Highway → Gandhinagar |
| `GJ 05 BL 9999` | Blacklisted sedan | Surat |

### Stolen-Vehicle Corridor Demo

```bash
docker compose exec worker python -m app.workers.demo_scenario
```

Then in the UI:
1. **Control Room** → watch alert inbox + map animate
2. **Search (Investigate)** → purpose: "Stolen Vehicle" → search `GJ 01 ST 0001`
3. See the GIS polyline across 5 junctions

### Government Feeds (Sentinel)

```
1. Control Room → Gov feeds tab
2. Click "Sync Sentinel"
3. Select a camera → HLS plays if .m3u8 available
4. Watchlist → add jury-issued plate
5. Wait for ANPR sampling (~10s per camera)
6. Search → ANPR report → Download CSV
```

---

## 13. Environment Configuration

Copy `.env.example` to `.env` before running locally.

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production…` | **Must change before real deployment** |
| `DATABASE_URL` | `postgresql+asyncpg://gusip:gusip@postgres:5432/gusip` | Async PG DSN |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `MINIO_ENDPOINT` | `minio:9000` | |
| `INFERENCE_MODE` | `simulate` | `simulate` (no GPU) or `yolo` (real) |
| `SIMULATION_ENABLED` | `true` | Runs 50-camera simulator |
| `SENTINEL_ENABLED` | `true` | Sentinel sync/ANPR |
| `SENTINEL_ANPR_INTERVAL_S` | `10.0` | Seconds between ANPR samples |
| `SENTINEL_BASE_URL` | `https://live.sentinelgujarat.in` | Official API |
| `USE_KAFKA` | `false` | Use Redpanda instead of Redis Streams |
| `AUDIT_ENABLED` | `true` | Write audit log entries |
| `ENCRYPTION_KEY` | `poc-dev-key-change-me-32bytes!!` | Evidence encryption |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | JWT lifetime (8 hours) |

---

## 14. Known Issues & Current State

### Local Dev Without Docker

Running `npm run dev` in `frontend/` shows:

```
[vite] http proxy error: /api/v1/auth/token
AggregateError [ECONNREFUSED]
```

This means the **backend is not running**. Options:

```bash
# Option A: Full Docker stack (recommended)
docker compose up -d

# Option B: Manual local dev
cd backend
pip install -r requirements.txt
# Start PostgreSQL + Redis locally first
python -m app.seed            # seed the database
uvicorn app.main:app --reload --port 8000

# In another terminal:
cd frontend && npm run dev
```

### Vite Proxy Config (`vite.config.ts`)

```typescript
proxy: {
  '/api': 'http://localhost:8000',
  '/ws':  { target: 'ws://localhost:8000', ws: true }
}
```

In Docker, Nginx handles proxying at port 8080 using `nginx.conf`.

---

## 15. Scale Path (PoC → 80,000 Cameras)

| Bottleneck | PoC (50 cameras) | Scale Solution (80k cameras) |
|---|---|---|
| API servers | 1 Uvicorn process | 2+ replicas behind load balancer |
| Workers | 1 background process | Horizontal GPU workers per zone/district |
| Message bus | Redis Streams | Kafka/Redpanda with partition-per-zone |
| Database | Single PostgreSQL | Patroni HA + read replicas; partition events by month |
| Object store | Local MinIO | S3-compatible + lifecycle (30-day clip retention) |
| Video | Not copied | On-demand relay via MediaMTX; full video stays at NVR |
| Auth | Local JWT | Keycloak + mTLS adapter certificates |

**Core insight:** 80,000 cameras does **not** mean copying 80,000 video streams to Gandhinagar. Only **events, stills, and short evidence clips** move to the centre. GPU workers are co-located with camera zones.

See [`docs/scalability.md`](docs/scalability.md) for detailed sizing tables.

---

## Related Documentation

| Document | Path |
|---|---|
| High-Level Design | [`docs/HLD.md`](docs/HLD.md) |
| Architecture | [`docs/architecture.md`](docs/architecture.md) |
| API Reference | [`docs/api.md`](docs/api.md) |
| Security Design | [`docs/security.md`](docs/security.md) |
| Scalability & Sizing | [`docs/scalability.md`](docs/scalability.md) |
| Deployment Guide | [`docs/deployment.md`](docs/deployment.md) |
| Cost-Benefit | [`docs/cost-benefit.md`](docs/cost-benefit.md) |
| SRS | [`docs/SRS.md`](docs/SRS.md) |
| Quick Start | [`README.md`](README.md) |

---

*Built for the Gujarat Police Innovation Challenge 2026. Intended for authorised law-enforcement evaluation only.*
