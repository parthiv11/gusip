# GUSIP Deployment Guide

## 1. Docker Compose (evaluation / PoC)

Prerequisites: Docker Engine 24+, Compose v2, 8 GB RAM recommended (4 GB minimum).

```bash
git clone <repo> gusip && cd gusip
cp .env.example .env
docker compose up -d --build
```

Services:

| Name | URL |
|---|---|
| Control room | http://localhost:8080 |
| API / OpenAPI | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 (gusip / gusipsecret) |

Seed runs automatically on API start. Worker emits detections every ~4s.

### Own-feed vs government-style demo

The 50-camera seed already mixes:

- `source_type=rtsp` — own-feed / NVR style
- `source_type=onvif` — typical municipal/police ONVIF
- `source_type=vendor_api` — Hikvision/Dahua/UNV style

No government network is contacted.

### GPU inference (optional)

```bash
# on a GPU node
pip install ultralytics
export INFERENCE_MODE=yolo
```

Point adapters at real RTSP URLs in the camera registry (`POST /api/v1/cameras`).

### Kafka-shaped bus

```bash
docker compose --profile full up -d
# set USE_KAFKA=true when the Kafka publisher path is enabled in a given build
```

PoC default bus is Redis Streams with the same event JSON, so swapping the transport does not change workers.

## 2. Local development (no Docker for apps)

```bash
# PostgreSQL 16 + PostGIS and Redis must be reachable
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://gusip:gusip@localhost:5432/gusip
python -m app.seed
uvicorn app.main:app --reload --port 8000

# other terminal
python -m app.workers.main

cd frontend
npm install
npm run dev   # http://localhost:5173
```

## 3. Kubernetes (production)

Manifests in `k8s/` are sized as a **city / state intelligence cluster** (API, GIS, watchlist, evidence), not the 80k-GPU farm. Resource table: `k8s/README.md`.

```bash
# edit gusip-secrets, ingress host, then:
kubectl apply -k k8s/
# regional GPU farm (NVIDIA device plugin + RuntimeClass nvidia)
kubectl apply -f k8s/gpu-worker.yaml
```

Included: ResourceQuota / LimitRange, StatefulSet + PVC (Postgres 200Gi, Redis 20Gi, MinIO 500Gi), requests/limits, probes, PDB, HPA, TLS Ingress, default-deny NetworkPolicy, optional GPU workers.

Replace in-cluster Postgres/MinIO with managed PostGIS and S3 before statewide. GPU counts for 80k cameras are in `docs/scalability.md`.

## 4. Hybrid on-prem

Recommended statewide pattern:

1. **District adapter VM or small K3s** next to the departmental VMS (pull only).
2. **Regional GPU farm** (Ahmedabad, Surat, Rajkot, Vadodara, Gandhinagar) for analytics workers.
3. **State intelligence cluster** (Gandhinagar / Ahmedabad DR pair) for watchlist, search, GIS, IdP.

Adapters never require inbound connections from the internet. They push events outbound to the regional bus over mTLS.

## 5. Backup

- PostgreSQL: WAL + nightly logical dump of registry, watchlist, alerts, audit
- Object store: versioned bucket, 90-day lifecycle on snapshots, legal-hold on case clips
- Redis/Kafka: treated as ephemeral; reconstruct from DB if needed

## 6. Demo checklist

1. Login as `operator`
2. Confirm video wall shows mixed `rtsp` / `onvif` / `vendor_api` badges
3. Wait for a red **stolen_vehicle** card or run `python -m app.workers.demo_scenario`
4. Acknowledge alert
5. Investigate plate `GJ 01 ST 0001` — route appears on GIS
6. Login as `admin` — audit rows for search/view/ack
