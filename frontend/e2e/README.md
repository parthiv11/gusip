# GUSIP end-to-end tests (Playwright)

Real-browser tests against a running GUSIP stack: login, RBAC, the Sentinel
Camera Grid video path, the camera registry, admin actions, and alert
evidence rendering. Not component/unit tests — see `backend/tests/test_core.py`
for backend unit + HTTP-integration coverage.

## Prerequisites

The full stack must already be running (these tests do **not** start it —
see `playwright.config.ts`):

```bash
cd .. && docker compose up -d --build
# wait for backend healthy: docker compose ps
```

## Running

```bash
npm ci
npx playwright install --with-deps chromium   # first run only
npm run test:e2e            # headless
npm run test:e2e:ui         # interactive UI mode, easier to debug
npm run test:e2e:report     # view the last HTML report
```

Point at a different deployment with `GUSIP_BASE_URL` (default
`http://localhost:8080`):

```bash
GUSIP_BASE_URL=https://gusip.example.in npm run test:e2e
```

## What's covered vs. what's flaky by nature

`control-room.spec.ts`'s "real video" test depends on the official Sentinel
Camera Grid actually being reachable and authenticated (see
`backend/app/services/sentinel_auth.py`) — that upstream is a third-party
evaluation service with its own occasional flakiness independent of GUSIP.
If it fails, check `docker compose logs worker` for Sentinel login/session
errors before assuming a regression.

`alerts.spec.ts`'s placeholder tests intercept the `/api/v1/alerts` response
to inject a missing/broken snapshot deterministically, rather than relying on
whichever demo data happens to be seeded — they should pass regardless of
what's in the database.
