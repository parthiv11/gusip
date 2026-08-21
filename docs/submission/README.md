# Hackathon form — files to upload

The Google Form needs **Google Drive (or similar) links**, not git paths. Upload these files from `docs/submission/`, set sharing to **Anyone with the link can view**, then paste the URLs.

Print HTML to PDF: open the file in Chrome → Print → Destination **Save as PDF** → Layout **Landscape** (presentation) or **Portrait** (HLD).

| Form field | File | How |
|---|---|---|
| **Solution presentation** (PDF/PPT/PPTX) | `presentation.html` → save as `GUSIP-presentation.pdf` | Chrome print to PDF, landscape |
| **High-level design / architecture** (PDF/PNG/JPG/SVG) | `architecture.svg` **or** `hld.html` → `GUSIP-HLD.pdf` | Prefer PDF of HLD + SVG as backup |
| **Workflow / integration diagram** (PDF/PNG/JPG/SVG) | `workflow.svg` | Upload SVG directly, or File → Open in Chrome → print PDF |
| **Screenshots folder** | `screenshots/` | See shot list below; upload the folder to Drive |
| **Solution video** | Record yourself | Must include **official Sentinel / provided data**, not only own/demo |
| **Any other document** | Optional | `docs/security.md`, `docs/scalability.md`, `docs/cost-benefit.md` as PDFs, or the GitHub repo URL |

## Video (required)

Form text: you may use own data **but you must also show their provided feeds**.

Record 3–5 minutes (OBS or phone of the screen), 1920×1080:

1. Login `operator` / `GUSIP@ops2026` — hybrid Model 1+2+3, VMS not replaced.
2. **Gov feeds** → Sync Sentinel → click an official camera (live.sentinelgujarat.in).
3. Own/demo wall + a watchlist hit auto-focus (`GJ 05 BL 9999` or stolen corridor).
4. Investigate `GJ 01 ST 0001` with purpose **evaluation** → GIS hops.
5. Mention coordinator break-glass and that operators cannot export.

Then upload to Drive and paste the link. Keep the file unlisted/anyone-with-link.

## Screenshots to capture into `screenshots/`

With `docker compose up` and http://localhost:8080:

1. `01-login.png`
2. `02-gov-feeds.png` — official Sentinel wall + large player
3. `03-own-demo-focus.png` — auto-focus pane on a watchlist hit
4. `04-gis.png`
5. `05-investigate.png` — plate search + map
6. `06-watchlist.png`
7. `07-alerts.png`
8. `08-rbac-coordinator.png` — login as coordinator, home-dept wall + Break-glass (optional)

## After you have Drive URLs

Paste them only in the form. Do not commit secrets. You can keep a private note of the URLs locally; they are not stored in this repo.
