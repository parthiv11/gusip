# Demo video / live readiness

A recorded walkthrough is not stored in git (binary). For the jury:

## Live path (preferred)

1. `docker compose up -d --build`
2. Browser 1920×1080 on http://localhost:8080
3. Narrate: hybrid federation, existing VMS untouched, three source types on the wall
4. Run `scripts/demo.sh` for the Ahmedabad→Gandhinagar stolen Fortuner
5. Show GIS polyline, alert ack, investigator search, admin audit
6. Open `docs/scalability.md` on the 80k GPU math

## Suggested 4-minute script

0:00 Purpose — 80k cameras, do not replace departmental VMS  
0:40 Architecture slide (docs/architecture.md mermaid)  
1:10 Login + 50-camera wall with RTSP/ONVIF/vendor badges  
1:50 Watchlist hit &lt; 8 s, acknowledge  
2:20 Journey reconstruction on GIS  
2:50 RBAC + audit  
3:10 Scale-out and cost (metadata not video)  
3:40 Q&A / live RTSP if a test camera is available  

Record with OBS or simple-screen-recorder when presenting.
