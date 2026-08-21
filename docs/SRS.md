# GUSIP Software Requirements Specification
# Gujarat Police Innovation Challenge 2026 — Version 1.0 — 18 August 2026
#
# The implementation in this repository is built against the SRS provided
# with the hackathon brief (hybrid Model 2 + Model 3 + Model 1).
#
# Traceability:
# FR-1 Camera registry & GIS     → cameras API, PostGIS, gap analysis, Leaflet
# FR-2 Ingestion & federation    → adapters (RTSP/ONVIF/vendor), reconnect loop
# FR-3 Unified viewing           → control-room grid, snapshots, live overlay
# FR-4 AI analytics              → pipeline + YOLO hook + ByteTrack-shaped IDs
# FR-5 Watchlist & alerts        → matching service, WebSocket inbox, ack
# FR-6 Search & investigation    → events/plate/track APIs, case export
# FR-7 Admin & security          → RBAC, audit, encryption, integration stubs
# NFR-1..6                       → see docs/scalability.md and docs/security.md
# PoC 50 cameras                 → app/seed.py
# Scale 80,000                   → docs/scalability.md
