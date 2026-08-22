# GUSIP API

Base URL (compose): `http://localhost:8000`  
OpenAPI: `http://localhost:8000/docs`

All console endpoints except `/health`, `/api/v1/meta`, `/api/v1/auth/token`, and `/api/v1/ingest/detection` require `Authorization: Bearer <jwt>`.

## Sentinel government feeds

| Method | Path |
|---|---|
| POST | `/api/v1/feeds/sentinel/sync` |
| GET | `/api/v1/feeds/sentinel/catalog` |
| GET | `/api/v1/feeds/sentinel/{id}/state` |
| GET | `/api/v1/feeds/sentinel/{id}/stream?token=` |
| GET | `/api/v1/feeds/sentinel/{id}/preview?token=` |
| GET | `/api/v1/feeds/anpr-report?fmt=json\|csv` |

Upstream: `https://live.sentinelgujarat.in` → catalogue **`GET /api/ingest`** (fallback `/api/cameras`).

- Inference / ANPR: `rtsp://<host>:8554/stream/<id>` with `rtsp_transport=tcp` (HLS if 8554 is blocked).
- Control-room wall: HLS `/live/stream/<id>/index.m3u8`, then HTTP `/stream/<id>` as browser fallback only.
- Do not `curl`/`wget` `/stream/<id>` as a file. Integrator guide: https://sentinel.gujarat.gov.in/resource


## Auth

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/auth/token` | OAuth2 password form |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/auth/users` | Admin create user |

Roles: `system_admin`, `department_coordinator`, `investigation_officer`, `control_room_operator`.

## Cameras & GIS (FR-1, FR-2)

| Method | Path |
|---|---|
| GET | `/api/v1/cameras` |
| GET | `/api/v1/cameras/departments` |
| GET | `/api/v1/cameras/{id}` |
| GET | `/api/v1/cameras/{id}/live` |
| POST | `/api/v1/cameras` |
| POST | `/api/v1/cameras/bulk` |
| GET | `/api/v1/gis/cameras` |
| GET | `/api/v1/gis/gaps` |
| GET | `/api/v1/gis/nearby?lat=&lon=&radius_m=` |

Filters: `department_id`, `status`, `source_type`, `city`, `camera_type`.

## Watchlist & alerts (FR-5)

| Method | Path |
|---|---|
| GET | `/api/v1/watchlist` |
| POST | `/api/v1/watchlist` |
| DELETE | `/api/v1/watchlist/{id}` |
| GET | `/api/v1/alerts` |
| POST | `/api/v1/alerts/{id}/ack` |

## Search & tracks (FR-6)

| Method | Path |
|---|---|
| POST | `/api/v1/search/events` |
| GET | `/api/v1/search/tracks/{global_track_id}` |
| GET | `/api/v1/search/plate/{plate}` |

Search body:

```json
{
  "plate": "GJ 01 ST 0001",
  "object_type": "vehicle",
  "camera_id": null,
  "event_type": "anpr",
  "city": "Ahmedabad",
  "from_ts": null,
  "to_ts": null,
  "color": "white",
  "vehicle_class": "suv",
  "limit": 100
}
```

## Cases

| Method | Path |
|---|---|
| GET/POST | `/api/v1/cases` |
| POST | `/api/v1/cases/{id}/evidence` |
| GET | `/api/v1/cases/{id}/export` |

Export is JSON metadata plus clip/snapshot URIs (standard clip + JSON as required).

## Admin & integrations

| Method | Path |
|---|---|
| GET | `/api/v1/admin/stats` |
| GET | `/api/v1/admin/audit` |
| POST | `/api/v1/integrations/lookup` |
| POST | `/api/v1/ingest/detection` |

`integrations/lookup` `source` ∈ `VAHAN | SARTHI | eGujCop | AFIS | NAFIS`. PoC returns `connected: false` with the production contract.

## Realtime

| Protocol | Path |
|---|---|
| WebSocket | `/ws/alerts?token=` |
| WebSocket | `/ws/live?token=` |

## Evidence

`GET /api/v1/evidence/snapshots/{name}?token=` — decrypts snapshot at rest.

## Example: login + search

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d 'username=investigator&password=GUSIP@inv2026' | jq -r .access_token)

curl -s -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"plate":"GJ 01 ST 0001"}' \
  http://localhost:8000/api/v1/search/events
```
