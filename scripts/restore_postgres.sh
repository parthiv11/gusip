#!/usr/bin/env bash
# Restore a logical dump produced by backup_postgres.sh (or the k8s backup
# CronJob's dump.sh) into the running `postgres` container.
#
# DESTRUCTIVE: this drops and recreates every object currently in the `gusip`
# database before restoring. Never run this against a database you have not
# deliberately decided to overwrite.
set -euo pipefail
cd "$(dirname "$0")/.."

DUMP_FILE="${1:-}"
if [ -z "$DUMP_FILE" ] || [ ! -f "$DUMP_FILE" ]; then
  echo "Usage: $0 <path-to-dump-file>" >&2
  echo "Dumps are created by scripts/backup_postgres.sh into ./backups/ by default." >&2
  exit 1
fi

echo "!! This will DROP and REPLACE every table in the 'gusip' database on the running postgres container."
echo "!! Dump file: ${DUMP_FILE}"
read -r -p "Type 'restore' to continue: " confirm
if [ "$confirm" != "restore" ]; then
  echo "Aborted."
  exit 1
fi

echo "Stopping backend/worker so they are not writing during restore..."
docker compose stop backend worker

echo "Restoring..."
docker compose exec -T postgres pg_restore -U gusip -d gusip --clean --if-exists --no-owner < "$DUMP_FILE"

echo "Restarting backend/worker..."
docker compose start backend worker

echo "Restore complete. Check 'docker compose logs backend worker' for a clean startup."
