# GUSIP API

Base URL (compose): `http://localhost:8000`  
OpenAPI: `http://localhost:8000/docs`

The browser uses an `HttpOnly`, `SameSite=Strict` session cookie. Unsafe requests also require the matching `X-CSRF-Token` header. Bearer JWTs remain available only for non-browser demo/API clients. `/api/v1/ingest/detection` uses its own signed-envelope authentication.

## Sentinel government feeds

| Method | Path |
|---|---|
| POST | `/api/v1/feeds/sentinel/sync` |
| GET | `/api/v1/feeds/sentinel/catalog` |
| GET | `/api/v1/feeds/sentinel/{id}/state` |
| GET | `/api/v1/feeds/sentinel/{id}/stream` |
| GET | `/api/v1/feeds/sentinel/{id}/preview` |
| GET | `/api/v1/feeds/anpr-report?fmt=json\|csv` |

Upstream live portal: `https://live.corp8.cloud` (the public ingest host). Catalogue **`GET /api/ingest`** is the contract — camera IDs and URLs are not hard-coded. Integrator guide: https://sentinel.gujarat.gov.in/resource

- AI / ANPR: catalogue `rtsp_url` over TCP. Primary client is OpenCV (`OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`, PTS from `CAP_PROP_POS_MSEC`); FFmpeg is the fallback. HLS if `:8554` is blocked. WHEP is browser preview only.
- Timing is PTS (`ffmpeg -copyts` / `CAP_PROP_POS_MSEC`), never reported FPS or wall-clock arrival. Inter-frame gaps are not disconnects. Loop cuts reset tracker epochs.
- Reconnect backoff 2–30s. Join decoder RPS/POC warnings are logged, not fatal. Mixed H.264/H.265 and mixed resolutions.
- Consume only. Do not publish to the gateway. Pace load (one live capture at a time).
- GUSIP `/sentinel/{id}/stream` proxies upstream `/stream/{id}` as a media-player range fallback. Do not `curl`/`wget` it as a file, and do not use it for inference.
- Browsers receive only authenticated GUSIP gateway URLs; upstream RTSP/HLS/WHEP addresses are redacted.


## Auth

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/auth/token` | OAuth2 password form |
| POST | `/api/v1/auth/logout` | Clear session and CSRF cookies |
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
| WebSocket | `/ws/alerts` |
| WebSocket | `/ws/live` |

## Evidence

`GET /api/v1/evidence/snapshots/{name}` — validates department scope, decrypts the snapshot and writes an audit event. Credentials never appear in the URL.

## Example: login + search

```bash
curl -s -c cookies.txt -X POST http://localhost:8000/api/v1/auth/token \
  -d 'username=investigator&password=GUSIP@inv2026' >/dev/null
CSRF=$(awk '$6 == "gusip_csrf" {print $7}' cookies.txt)

curl -s -b cookies.txt -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d '{"plate":"GJ 01 ST 0001","purpose":"stolen_vehicle"}' \
  http://localhost:8000/api/v1/search/events
```
