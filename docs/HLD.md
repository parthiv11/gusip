# GUSIP High-Level Design

**Project:** Gujarat Unified Surveillance Intelligence Platform  
**Version:** 1.0 · **Date:** 18 August 2026  
**Approach:** Hybrid Model 2 (federation) + Model 3 (central AI) + Model 1 (GIS registry)

## 1. Problem

Gujarat’s CCTV estate is large, departmental, and heterogeneous (police, traffic, municipal, highway, railway, coastal). Replacing every VMS is neither affordable nor operationally acceptable. The force still needs statewide watchlist matching, multi-camera tracking, and a single control-room picture.

## 2. Design principles

1. **Do not break source operations.** Adapters are read-oriented. Departmental VMS/NVR remain system of record for full video.
2. **Centralise intelligence, not video.** Metadata, events, embeddings, alerts, and short evidence clips move to the centre. Full streams stay at the edge unless an operator requests a relay.
3. **Federation before replacement.** RTSP, ONVIF Profile S/T, and vendor SDKs coexist.
4. **Zero-trust internally.** Every hop authenticated; every query audited.
5. **Horizontal workers.** Ingestion, inference, tracking, and matching scale independently.

## 3. Logical architecture

```
Departmental VMS / NVR / Cloud
        |  RTSP / ONVIF / vendor API (read-only)
Ingestion / Adapter Layer
        |  normalised frames (sampled) + camera telemetry
Federation Middleware
        |  authn, protocol translation, Kafka/Redis event bus
Central Intelligence Layer
        |  viewer · YOLO/track · Re-ID · ANPR · watchlist · alerts · search · GIS
Data stores          Frontend (React control room)
PostgreSQL+PostGIS   Object store (clips)
Vector/OS search     IdP + audit
```

## 4. Mapping to SRS models

| Model | GUSIP realisation |
|---|---|
| Model 1 GIS registry | Camera master with PostGIS, health, AMC, gap analysis |
| Model 2 federation | Per-department adapters; existing VMS untouched |
| Model 3 intelligence | GPU workers + watchlist engine + unified console |

## 5. Runtime building blocks (PoC)

| Block | PoC choice | Production swap |
|---|---|---|
| API | FastAPI | Same, replicated behind API gateway |
| Event bus | Redis Streams (+ Redpanda profile) | Kafka / Redpanda with ACLs |
| Metadata / GIS | PostgreSQL 16 + PostGIS | Patroni / Cloud SQL + PostGIS |
| Evidence | Encrypted files + MinIO | S3-compatible with KMS + lifecycle |
| Auth | JWT RBAC | Keycloak + mTLS to adapters |
| AI | Simulator contract ≡ YOLO | YOLOv8/RT-DETR + ByteTrack + OSNet + Indian ANPR |
| UI | React + Leaflet | Same, video wall via MediaMTX/GPU decode |

## 6. Data that is allowed to leave a department

- Camera registry fields and health
- Detection metadata (class, plate, track id, confidence, bbox)
- Re-ID embedding (not reversible to a face image)
- Snapshot / 8–15s clip **on event or operator request**
- Alerts

Full 24×7 bitstream is **not** copied statewide (NFR-6).

## 7. Key flows

### 7.1 Live watchlist hit

1. Adapter samples stream from source VMS (or simulator emits equivalent event).
2. Inference worker detects vehicle/person, tracks, reads plate, embeds appearance.
3. Federation bus carries a normalised `detection` event.
4. Matching service compares plate / embedding to active watchlist.
5. Alert engine writes row, stores encrypted snapshot, publishes WebSocket.
6. Operator acknowledges; audit log records view + ack.

Target: **&lt; 8 seconds** camera-to-inbox on the PoC path.

### 7.2 Investigation reconstruction

Search by plate / attributes / time / camera → ordered `track_points` → GIS polyline + case folder export (JSON + clip references).

### 7.3 Source outage

If a departmental VMS is unreachable, that adapter marks cameras offline. Other departments continue. Auto-reconnect restores `online` (NFR-3).

## 8. PoC scope (demonstrable)

- 50 cameras across 10 cities / 11 departments
- Three source types: RTSP, ONVIF, vendor API
- Stolen vehicle corridor Ahmedabad → Gandhinagar
- GIS, alerts, RBAC, audit, case export
- Documented 80k scale-out

## 9. Out of scope for PoC (interfaces reserved)

Live VAHAN, SARTHI, eGujCop, AFIS, NAFIS calls. REST envelopes exist under `/api/v1/integrations/lookup` and must be bound to department-issued mTLS certificates before production use.
