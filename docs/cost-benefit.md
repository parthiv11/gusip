# GUSIP Cost-Benefit Summary

## 1. Cost avoided (why hybrid wins)

A “rip and replace + central 80k VMS” programme typically prices:

- New central VMS licences per camera
- 80k × 24×7 bitstream storage (petabytes)
- Statewide dark fibre / huge WAN
- Retraining every departmental operator on a new VMS

GUSIP **keeps paying AMC on existing NVRs** and adds a thin intelligence overlay. Full video remains where it already is.

Indicative 5-year opex contrast (order-of-magnitude, not a bid):

| Item | Full central VMS | GUSIP hybrid |
|---|---|---|
| Central video storage | Very high | Low (clips + snapshots) |
| WAN | Very high | Moderate (events + on-demand) |
| GPU analytics | High either way | High, but regional and incremental |
| Adapter / integration | Medium | Medium (the actual new spend) |
| Licence disruption | High | Low |
| Department retraining | High | Low (source VMS unchanged) |

The dominant saving is **not storing and hauling 80,000 continuous streams**.

## 2. What the overlay must still fund

- Regional GPU farms (largest new capex)
- Kafka + search + PostGIS HA
- Adapter software maintenance per OEM
- Security (IdP, SOC review of audit, KMS)
- 24×7 intelligence-desk staffing (process, not only software)

## 3. Benefits (police outcomes)

| Outcome | Mechanism |
|---|---|
| Faster stolen-vehicle recovery | Statewide ANPR + watchlist &lt; 8 s in PoC path |
| Multi-jurisdiction pursuit | Re-ID + GIS journey, not phone calls between control rooms |
| Missing person / wanted | Same event bus, human acknowledgement |
| Coverage planning | Gap analysis from the camera registry (Model 1) |
| Accountability | Immutable-style audit of every view/search |
| Continuity | One VMS outage does not blank the state picture |

## 4. PoC cost envelope

The evaluation stack runs on a single workstation or small VM:

- 4–8 vCPU, 8 GB RAM, 20 GB disk
- No GPU required for the simulated demo
- All open-source components (PostgreSQL, Redis, FastAPI, React, MinIO, optional Redpanda)

City-pilot increment: 1–2 servers + 1–2 GPUs + existing cameras.

## 5. Risk of *not* federating

- Parallel watchlists that never meet
- Investigators reconstructing journeys by hand
- New camera purchases without GIS gap evidence
- Vendor lock-in if a single OEM is chosen as the “state VMS”

## 6. Recommendation

Fund GUSIP as **intelligence middleware + regional AI**, not as a statewide NVR. Use this PoC to prove the event contract with two live source types, then attach real ONVIF/RTSP in one commissionerate before buying GPU at scale.
