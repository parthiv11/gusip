# GUSIP Scalability & Infrastructure Sizing

## 1. Scaling thesis

Do **not** centralise 80,000 full video streams. Centralise **events**. Decode and AI happen in regional farms. The state layer stores metadata, embeddings, alerts, and short evidence.

This is the only cost-effective path that still yields statewide watchlist and journey reconstruction.

## 2. Horizontal axes (NFR-2)

| Axis | How it scales | 50-cam PoC | 80,000-cam |
|---|---|---|---|
| Adapters | One deployment per department / cluster of NVRs | 1 worker process | ~200–400 adapter pods |
| Inference | GPU workers consume camera shards from the bus | simulator | ~400–800 GPU workers |
| Matching | Stateless, sharded by plate hash | in-API | 20–40 pods |
| API / search | Replicas behind ingress | 1 | 12–24 |
| GIS / registry | PostgreSQL + PostGIS | 1 | HA pair + read replicas |
| Event bus | Redis → Kafka partitions by `camera_id` | Redis | 12+ brokers, 80k partitions not required — hash to ~600 partitions |
| Object store | MinIO / S3 | 1 | Multi-AZ bucket, lifecycle |

## 3. Traffic model (order-of-magnitude)

Assumptions for statewide:

- 80,000 cameras, 15–25 fps source, **AI sampled at 5 fps** average (higher on watchlist corridors)
- ~30% cameras with ANPR; rest detection/track only
- Average 0.2 events/camera/second after filtering parked scenes → **16,000 events/s** peak statewide
- Alerts (watchlist) ≪ 1% of events → a few tens per second statewide

Event JSON ~1–2 KB. Bus throughput ~ 30–60 MB/s — well within Kafka.

Evidence: 1 snapshot (~80 KB) per alert + 10 s clip (~3 MB) on confirm. At 20 confirmed alerts/s → ~60 MB/s object write (burst). Lifecycle to glacier after 90 days except legal hold.

## 4. GPU sizing

YOLOv8n TensorRT on a modern data-centre GPU (L4 / A2 / T4 class) typically handles **20–40 1080p streams** at 5–10 fps with tracking, depending on scene density.

| Cameras | GPU class | GPU count (with N+1) |
|---|---|---|
| 50 (PoC) | none (simulate) or 1× T4 | 0–1 |
| 5,000 (city) | L4 | ~150–200 |
| 80,000 (state) | mixed L4/L40 | ~2,000–3,500 **regionally distributed** |

Re-ID (OSNet) and ANPR can share the same node or sit on a second queue.

**Do not put all GPUs in one hall.** Place farms next to dense camera regions (Ahmedabad, Surat, Vadodara, Rajkot, rest-of-Gujarat) to cut WAN video-sample traffic.

## 5. WAN and low-bandwidth operation

Geographical spread ~1000 km (SRS). Adapters send **events**, not 24×7 video:

- 80k cameras × 2 KB/s event metadata ≈ 160 MB/s statewide **if naïve**
- After edge filtering (empty frames dropped) design target **20–40 MB/s** into the state Kafka

On-demand live relay: budget a transcode pool (e.g. 200 concurrent control-room views statewide, not 80k).

Low-bandwidth / degraded-link strategy, in order of what the link loses first:

1. **Live relay drops before events do.** The control-room wall is the first thing to fail gracefully — a camera can be "offline for viewing" while the adapter still ships ANPR/detection events at a few KB/s. Watchlist correlation and alerting do not need a human watching a picture.
2. **Exponential retry backoff, not hammering a bad link.** The PoC's Sentinel adapter already does this on RTSP failure — `_mark_rtsp_failure`/`_mark_rtsp_success` in `backend/app/workers/sentinel.py` double the retry delay (capped at 30s) per consecutive failure and reset on success, falling back to HLS meanwhile. Production adapters extend the same idea to inference itself: downgrade sampled FPS (5 fps → 1 fps → keyframe-only) under sustained loss rather than buffering unboundedly.
3. **Edge-local disk buffer, drain on recovery.** §8 below — a WAN-down department queues events locally instead of losing them.
4. **Evidence clips are pulled, not pushed.** Only a snapshot (~80 KB) rides the primary event; the short clip is fetched on-demand when an operator opens the alert, so a slow link isn't paying for clips nobody looks at.
5. **HLS/adaptive relay for the one link that does carry video** (operator preview) instead of raw RTSP restreamed statewide — same reasoning as why the PoC proxies Sentinel HLS through the API rather than exposing raw RTSP to browsers.

## 6. Data stores at 80k

| Store | 3-year volume (indicative) |
|---|---|
| Camera registry | &lt; 1 GB |
| Events (hot 90 days) | 50–150 TB compressed JSON/columnar (or downsample) |
| Track points | subset of events |
| Embeddings | OpenSearch kNN / pgvector / Milvus — keep 14–30 days hot |
| Audit | 1–5 TB |
| Evidence clips | 200–800 TB with lifecycle; legal hold separate |

Hot search: OpenSearch for plate/attribute; PostGIS for cameras/tracks.

## 7. PoC → state growth path

1. **PoC (this repo):** 50 cameras, one compose stack, simulator + optional YOLO.
2. **City pilot (500–2,000 cams):** attach real RTSP/ONVIF for 2+ vendors; 4–8 GPUs; Kafka; Keycloak.
3. **Range / commissionerate:** adapter appliance per department; regional GPU.
4. **Statewide:** five regional farms + active-active intelligence in two AZs; DR drill.

Each stage keeps the **same event contract**, so software does not fork.

## 8. Monitoring, logging, and health checks

Already in the PoC, not just planned:

- **Metrics:** `GET /metrics` (Prometheus text format) — request counters and a latency histogram per route, via `backend/app/core/metrics.py`. Scrapeable by any standard Prometheus/Grafana stack without code changes at production scale.
- **Structured logging:** every log line carries a request ID propagated through the `X-Request-ID` response header (`backend/app/core/logging.py`), so one request's log lines can be traced across API and worker processes instead of grepping unstructured stdout per replica. `GUSIP_LOG_JSON=1` switches to machine-parseable JSON for a log aggregator (Loki/ELK).
- **Liveness vs readiness, split on purpose:** `GET /health` only answers "is the process up" — no dependency calls, so a slow DB never fails a liveness probe and triggers a pointless restart. `GET /ready` actually checks Postgres and Redis reachability and reports per-dependency status, for the orchestrator to gate traffic on.

Production scale-out is the same primitives, more of them: per-service dashboards, alerting on the existing latency histogram (p95/p99 SLOs), adapter-level "last frame received" staleness alarms (a camera going quiet is itself a signal worth alerting on, independent of AI health), and log/metric retention split hot (searchable, 30–90 days) vs cold (compliance archive).

## 9. Reliability, backup, and disaster recovery

Load balancing / horizontal scaling: every stateless tier (API, adapters, matching workers) already scales by replica count (§2); the only stateful tiers are Postgres, Redis, and the object store, each with a named production HA pattern below.

| Aspect | PoC | Production |
|---|---|---|
| Adapter → bus during WAN outage | — | Local disk buffer per adapter; drains to the bus on reconnect rather than dropping events |
| Event bus durability | Redis, single node | Kafka, replication factor 3, per-department topic partitioning |
| Database HA | Single Postgres container | Postgres synchronous standby for alerts/watchlist (no silent data loss on primary failure); async read replicas for search/GIS load |
| Object store | Single MinIO container | Multi-AZ bucket with lifecycle rules (hot → glacier per §6); versioning on the watchlist/case buckets |
| Backups | — (PoC has no production data to protect) | Encrypted, offsite, dual-control restore (security.md §4); nightly Postgres base backup + continuous WAL archiving for point-in-time recovery |
| DR posture | — | Active-active intelligence layer across two AZs (§7); documented, rehearsed DR drill — not just a failover script that has never been run |
| Graceful degradation | GIS/registry stay up if the AI farm is down; the AI farm keeps detecting/alerting if the console is down — these are separate services in this PoC's own compose stack, not a single monolith that fails as one unit | Same property, enforced by the network policy in security.md §3 (console never talks directly to Kafka/DB) |

The degradation property is deliberate, not incidental: because adapters, inference, the event bus, and the console are separate processes talking through an event contract (not a single monolith), a failure in one does not cascade into "no visibility statewide" — it narrows to "no visibility from the cameras/service that's actually down."
