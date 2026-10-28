#!/usr/bin/env bash
# Update TryOnU on the VPS with almost no downtime:
#   bash /var/www/tryonu/deploy/update.sh
#
# The website is built BESIDE the running one (.next-build), and only swapped in
# when the build has finished, so visitors and search engines never hit the
# 1-2 minutes of errors a build in place caused. If the new version doesn't
# answer after the swap, the previous one is put back by itself.
#
# Everything is inside main() so that `git pull` changing this file while it
# runs can't confuse bash.

main() {
  set -euo pipefail
  local ROOT=/var/www/tryonu
  local SITE=https://tryonu.app

  echo "== Getting the new code"
  cd "$ROOT"
  git pull origin tryon-fixes
  echo "   Version: $(git log -1 --format=%h)"

  echo "== API and worker"
  cd "$ROOT/apps/api"
  ./.venv/bin/pip install -q -r requirements.txt
  ./.venv/bin/python -m alembic upgrade head
  pm2 restart tryonu-api
  # never cut off a try-on that's being drawn (waits up to 4 minutes)
  ./.venv/bin/python -m app.scripts.wait_worker_idle --max 240 || true
  pm2 restart tryonu-worker

  echo "== Website: building beside the running site (the site stays up)"
  cd "$ROOT/apps/web"
  rm -rf .next-build
  NEXT_DIST_DIR=.next-build npm run build
  local APP=.next-build/standalone/apps/web
  cp -r .next-build/static "$APP/.next-build/static"
  if [ -d public ]; then cp -r public "$APP/"; fi

  echo "== Switching to the new website"
  rm -rf .next-old
  if [ -d .next ]; then mv .next .next-old; fi
  mv .next-build .next
  pm2 restart tryonu-web

  # the new site must answer; otherwise the previous one goes back
  local code=000
  for _ in $(seq 1 20); do
    sleep 2
    code=$(curl -s -o /dev/null -w "%{http_code}" "$SITE/robots.txt" || true)
    if [ "$code" = "200" ]; then break; fi
  done
  if [ "$code" != "200" ]; then
    echo "!! The new website didn't start (HTTP $code). Putting the previous version back."
    if [ -d .next-old ]; then
      rm -rf .next-broken
      mv .next .next-broken
      mv .next-old .next
      pm2 restart tryonu-web
    fi
    echo "!! Send the output of: pm2 logs tryonu-web --lines 60 --nostream"
    exit 1
  fi
  echo "   Website is up (HTTP 200)."

  echo "== Nightly backups"
  # the database every night (kept 7 days), photos every Sunday, into /var/backups/tryonu
  chmod +x "$ROOT/deploy/backup.sh"
  if ! crontab -l 2>/dev/null | grep -q "deploy/backup.sh"; then
    (crontab -l 2>/dev/null; echo "30 2 * * * bash $ROOT/deploy/backup.sh >> /var/log/tryonu-backup.log 2>&1") | crontab -
    echo "   Installed: every night at 02:30 (server time)."
  else
    echo "   Already on."
  fi

  echo "== Telling Bing and other search engines"
  cd "$ROOT/apps/api"
  ./.venv/bin/python -m app.scripts.indexnow_ping || echo "   (IndexNow ping failed; the site update itself is fine)"

  echo "== Done: $(cd "$ROOT" && git log -1 --format=%h)"
}

main "$@"
