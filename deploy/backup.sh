#!/usr/bin/env bash
# TryOnU's nightly backup, run by cron (update.sh installs it):
#   - every night: the database (pg_dump), kept 7 days
#   - every Sunday: the photos and files (apps/api/storage), kept 2 weeks
# into /var/backups/tryonu. Download them with WinSCP/FileZilla now and then:
# a copy only on the same server doesn't survive the server.
set -euo pipefail

DIR=/var/backups/tryonu
ROOT=/var/www/tryonu
DAY=$(date -u +%F)
mkdir -p "$DIR"
chmod 700 "$DIR"

# the database name from the API's settings (DATABASE_URL), tryonu_db if it can't be read
DB=$(grep -E '^DATABASE_URL=' "$ROOT/apps/api/.env" 2>/dev/null | sed -E 's#.*/([A-Za-z0-9_]+)(\?.*)?["'"'"']?$#\1#' || true)
DB=${DB:-tryonu_db}

sudo -u postgres pg_dump -Fc "$DB" > "$DIR/db-$DAY.dump.part"
mv "$DIR/db-$DAY.dump.part" "$DIR/db-$DAY.dump"
find "$DIR" -name 'db-*.dump' -mtime +7 -delete

if [ "$(date -u +%u)" = "7" ]; then
  tar czf "$DIR/files-$DAY.tar.gz.part" -C "$ROOT/apps/api" storage
  mv "$DIR/files-$DAY.tar.gz.part" "$DIR/files-$DAY.tar.gz"
  find "$DIR" -name 'files-*.tar.gz' -mtime +15 -delete
fi

echo "$(date -u +%FT%TZ) backup ok: $(ls -1 "$DIR" | wc -l) files, $(du -sh "$DIR" | cut -f1)" >> "$DIR/backup.log"
