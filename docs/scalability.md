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

## 5. WAN

Geographical spread ~1000 km (SRS). Adapters send **events**, not 24×7 video:

- 80k cameras × 2 KB/s event metadata ≈ 160 MB/s statewide **if naïve**
- After edge filtering (empty frames dropped) design target **20–40 MB/s** into the state Kafka

On-demand live relay: budget a transcode pool (e.g. 200 concurrent control-room views statewide, not 80k).

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

## 8. Reliability

- Adapter local buffer (disk) when WAN down; drain later
- Kafka replication factor 3
- Postgres synchronous standby for alerts/watchlist
- Graceful degradation: GIS and registry work if AI farm is down; AI farm works if console is down
