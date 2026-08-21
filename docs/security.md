# GUSIP Security Architecture Note

**Classification:** For authorised Gujarat Police evaluation  
**PoC vs production:** PoC demonstrates controls; production must complete the hardening list in §7.

## 1. Threat model (summary)

| Threat | Mitigation |
|---|---|
| Unauthorised viewing of cameras | RBAC (department + role); coordinator scoped to own department |
| Insider browsing / leakage | Full audit of login, view, search, export, ack |
| Tampering with watchlist | Restricted write roles; audit |
| Video interception | TLS in transit; encrypted snapshots at rest |
| Adapter abuse | Shared adapter key (PoC) → mTLS client certs (prod) |
| Supply-chain / lateral movement | Segmented namespaces; no inbound to departmental VMS |
| Prompted bulk export | Case export audited; no statewide raw dump API |

This platform is for **lawful policing** (stolen vehicles, wanted/missing persons, traffic intelligence). It is not a general-purpose covert surveillance toolkit.

## 2. Identity and access

PoC: signed JWT (HS256) with `sub`, `role`, `dept`.  
Enforcement is **RBAC on the glass, ABAC underneath** (NIST SP 800-162): action, home department, investigation purpose, and optional time-boxed break-glass.  
Production: Keycloak (or department IdP) with OIDC, short-lived tokens, MFA for admins, group → department mapping.

Roles (FR-7.1) — four visible roles, capabilities computed server-side:

| Role | Typical actions | Scope |
|---|---|---|
| Control room operator | Live wall, ack alerts, GIS, purpose-bound search | Statewide SOC |
| Investigation officer | Search (purpose required), watchlist write, case export | Statewide |
| Department coordinator | Own-department cameras; break-glass for other districts (reason + TTL + extra audit) | Home department unless break-glass |
| System admin | Users, bulk onboard, full audit | Statewide |

Purpose values on Investigate: `stolen_vehicle`, `blacklisted_vehicle`, `wanted_person`, `missing_person`, `traffic_incident`, `law_and_order`, `evaluation`. Empty/unknown purpose is rejected. CSV / case export is denied to operators.

Break-glass: `POST /api/v1/auth/break-glass` stores a Redis TTL grant. `GET /api/v1/auth/me` returns `scope` and `capabilities` so the UI can hide buttons the API would reject.

## 3. Zero trust between components (NFR-4)

Production pattern:

- Workload identity (SPIFFE) or mesh mTLS (Linkerd/Istio) for adapter → bus → API
- Kafka ACLs per department topic prefix `dept.{code}.events`
- NetworkPolicy: adapters cannot reach Postgres; only the API and matching workers can
- Control-room browsers talk only to ingress, never to Kafka or DB

PoC compose is a single network for evaluability.

## 4. Encryption

| Data | PoC | Production |
|---|---|---|
| In transit | HTTP inside compose | TLS 1.2+ everywhere; mTLS adapters |
| Snapshots at rest | Fernet (AES) via `ENCRYPTION_KEY` | KMS-backed envelope encryption |
| Database | Disk encryption of host | TDE / LUKS + KMS |
| Backups | — | Encrypted, offsite, dual control |

## 5. Audit (FR-7.2)

`audit_logs` records user, action, resource, JSON details, IP, timestamp for:

- login, list/view cameras, GIS, searches, plate routes, track views
- watchlist mutations, alert ack, case create/export
- break-glass grant/revoke (reason + duration + expiry)
- ANPR CSV export

Admin UI: `/admin`. Retention target in production: **7 years** for access logs (align with departmental record rules).

## 6. External government systems (FR-7.4)

`POST /api/v1/integrations/lookup` is an **interface only**. It does not query VAHAN/SARTHI/eGujCop/AFIS/NAFIS from the PoC. Binding those systems requires:

- Legal MoU and purpose limitation
- Department-issued client certificates
- IP allowlists
- Field-level minimisation (no bulk dump)
- Separate audit stream

## 7. Production hardening checklist

- [ ] Rotate `SECRET_KEY`; use RS256/JWKS from Keycloak
- [ ] Disable `CORS *`; pin console origins
- [ ] Replace adapter shared key with per-department mTLS
- [ ] WAF + SSO in front of console
- [ ] Secret scanning in CI; no credentials in git
- [ ] Vulnerability scanning of images (Trivy)
- [ ] Pen-test adapters so they cannot PTZ/write to source VMS
- [ ] DPDP / police data SOPs: retention, access justification, victim/witness protection flags
- [ ] Red-team the watchlist path (false-positive handling, human-in-the-loop)

## 8. Secure development notes

- Path traversal blocked on evidence files
- Passwords bcrypt-hashed
- SQLAlchemy bound parameters
- Snapshots stored outside the git tree
