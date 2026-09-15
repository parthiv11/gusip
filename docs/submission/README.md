# Hackathon form — paste these links

**Submission deadline: 28 September 2026** (extended from an earlier date — confirmed on sentinel.gujarat.gov.in). Event: 12–13 Oct 2026.

Public GitHub repo: **https://github.com/parthiv11/gusip**

Copy the URL in the **Paste this** column into the Google Form. Files are already on `main`.

| Form field | Paste this |
|---|---|
| **Solution presentation** (PDF / PPT / PPTX) | https://github.com/parthiv11/gusip/raw/main/docs/submission/GUSIP-presentation.pdf |
| **High-level design / architecture** (PDF / PNG / JPG / JPEG / SVG) | https://github.com/parthiv11/gusip/raw/main/docs/submission/architecture.svg |
| **Workflow / integration diagram** (PDF / PNG / JPG / JPEG / SVG) | https://github.com/parthiv11/gusip/raw/main/docs/submission/workflow.svg |
| **Screenshots folder** | https://github.com/parthiv11/gusip/tree/main/docs/submission/screenshots |
| **Solution video** (Google Drive) | Recorded file: `docs/submission/GUSIP-demo.mp4` (2:12, 1080p, voiceover + captions). **Upload that file to Google Drive**, share Anyone with the link, paste the Drive URL. GitHub will not satisfy this field. |
| **Government-feed ANPR output report** (required — "detected vehicles/plates with timestamps") | https://github.com/parthiv11/gusip/raw/main/docs/submission/sentinel-gov-feed-anpr-report.csv |
| **Any other document** | https://github.com/parthiv11/gusip |

## Backup links (same files)

| Field | Alternate |
|---|---|
| Presentation (HTML, print to PDF if a judge prefers slides) | https://github.com/parthiv11/gusip/blob/main/docs/submission/presentation.html |
| HLD PDF | https://github.com/parthiv11/gusip/raw/main/docs/submission/GUSIP-HLD.pdf |
| HLD HTML | https://github.com/parthiv11/gusip/blob/main/docs/submission/hld.html |
| Security / scale / cost | https://github.com/parthiv11/gusip/blob/main/docs/security.md · https://github.com/parthiv11/gusip/blob/main/docs/scalability.md · https://github.com/parthiv11/gusip/blob/main/docs/cost-benefit.md |

## Video (required — Drive only)

File on disk / GitHub: [GUSIP-demo.mp4](https://github.com/parthiv11/gusip/raw/main/docs/submission/GUSIP-demo.mp4)  
1920×1080 · 2:12 · on-screen captions + AI voiceover narration (edge-tts) · official Sentinel wall (`live.corp8.cloud`) is in the first minute.

What it shows:

1. Title card — GUSIP, Gujarat Police Innovation Challenge 2026
2. Operator wall — Gov feeds, Chimanbhai Bridge live through the GUSIP Sentinel proxy
3. Own/demo wall — RTSP/ONVIF/vendor cameras, watchlist: stolen Fortuner GJ 01 ST 0001
4. Corridor firing → hit landed — GJ 01 ST 0001 flagged on the wall in seconds
5. Investigate — mandatory audited purpose, then the GIS polyline (five hops, two cities)
6. Statewide GIS — cameras, coverage, open-alert pins
7. Ahmedabad coordinator — home-district-only cameras, then break-glass (audited FIR reason, time-boxed statewide access)
8. End card

Built with a small in-repo pipeline (all against the live local stack at `localhost:8080`):
1. `capture_raw.py` — Playwright walkthrough recorded with Chromium's native video capture, plus a `remotion/src/meta.ts` timeline of caption timestamps.
2. `docs/submission/remotion` — a small React/Remotion project renders just the title and end cards (fast; no video decode).
3. `burn_captions.py` — ffmpeg `drawtext` burns the on-screen captions onto the raw walkthrough footage, timed from `meta.ts`.
4. `generate_voiceover.py` — edge-tts (free, no API key) narrates the same caption lines into a mixed, correctly-timed audio track.
5. ffmpeg concatenates title + captioned walkthrough + end card, then muxes in the narration track, to produce `GUSIP-demo.mp4`.

Re-running end to end: `python3 docs/submission/capture_raw.py && python3 docs/submission/burn_captions.py && python3 docs/submission/generate_voiceover.py`, then render the Remotion title/end cards and concat/mux with ffmpeg (see git history for the exact commands used).

**Form will reject a GitHub URL here.** Download the mp4, upload to Google Drive → Anyone with the link can view → paste that Drive link.

## Government-feed ANPR output report

The problem statement requires a separate output report for the Government-feed demonstration: "a screen-recorded video along with an output report showing detected vehicles or number plates with corresponding timestamps." The video covers the screen recording; [`sentinel-gov-feed-anpr-report.csv`](sentinel-gov-feed-anpr-report.csv) is the report — 60 real ANPR detections produced by the running pipeline against the actual jury-provided Sentinel cameras (not simulated), each with timestamp, camera code/name/city, plate read, confidence, and track id. Regenerate it any time with:

```sql
COPY (
  select e.timestamp at time zone 'utc' as timestamp_utc, c.code as camera_code, c.name as camera_name,
         c.city, e.attributes->>'official_location' as official_location, e.plate_number,
         e.plate_normalized, e.confidence, e.global_track_id
  from detection_events e join cameras c on c.id = e.camera_id
  where e.event_type = 'anpr' and e.attributes->>'source_type' = 'sentinel'
  order by e.timestamp desc
) TO STDOUT WITH CSV HEADER
```
(or hit `GET /api/v1/feeds/anpr-report?fmt=csv` as investigator/coordinator/admin, then filter to `source=sentinel` — the API endpoint mixes all camera sources by default.)

## Screenshots already in the folder

1. `01-login.png`
2. `02-gov-feeds.png` — official Sentinel wall
3. `03-own-demo-focus.png` — enlarged official camera
4. `04-gis.png`
5. `05-investigate.png`
6. `06-watchlist.png`
7. `07-alerts.png`
8. `08-rbac-coordinator.png`
