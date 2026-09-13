#!/usr/bin/env bash
# Nightly-style logical backup for the docker-compose PoC path.
# k8s production uses the equivalent CronJob in k8s/backup.yaml instead —
# keep the two in sync if you change the retention window or dump format.
#
# Schedule this with host cron/systemd-timer, e.g.:
#   0 2 * * *  cd /path/to/gusip && ./scripts/backup_postgres.sh >> /var/log/gusip-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

OUT_DIR="${GUSIP_BACKUP_DIR:-./backups}"
RETENTION_DAYS="${GUSIP_BACKUP_RETENTION_DAYS:-30}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DUMP_NAME="gusip-${STAMP}.dump"

mkdir -p "$OUT_DIR"
echo "Dumping Postgres -> ${OUT_DIR}/${DUMP_NAME}"
docker compose exec -T postgres pg_dump -U gusip -d gusip -Fc > "${OUT_DIR}/${DUMP_NAME}"

echo "Dump size: $(du -h "${OUT_DIR}/${DUMP_NAME}" | cut -f1)"

echo "Pruning local dumps older than ${RETENTION_DAYS} days"
find "$OUT_DIR" -name 'gusip-*.dump' -mtime "+${RETENTION_DAYS}" -print -delete

echo "Done. Restore with: ./scripts/restore_postgres.sh ${OUT_DIR}/${DUMP_NAME}"
