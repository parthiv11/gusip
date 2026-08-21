#!/usr/bin/env bash
set -euo pipefail
echo "GUSIP live demo helper"
echo "1. Open http://localhost:8080  (operator / GUSIP@ops2026)"
echo "2. Trigger stolen-vehicle corridor..."
docker compose exec -T worker python -m app.workers.demo_scenario
echo "3. Investigate plate GJ 01 ST 0001"
echo "4. Admin audit: admin / GUSIP@admin2026"
