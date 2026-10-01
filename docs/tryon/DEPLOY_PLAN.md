# Production DB migration deploy plan — NOT executed, for review only

**Correction, 2026-10-01:** this document originally claimed production was 10 migrations behind, based on checking a Supabase database via the local dev `.env`. That Supabase project is **not** production — confirmed by reading the VPS's own `.env` (`DATABASE_URL=postgresql+asyncpg://tryonu:***@localhost:5432/tryonu_db`, a local Postgres instance on the VPS itself) and by running `alembic current` there directly: **real production is at `e4b8c1d90a37` — fully current with `main`, not behind at all.** See memory `production_db_is_local_postgres_on_vps.md`.

The only pending migration is `a1f6c3d8b254` (`distractor_options` on `tryon_jobs`), added this session on the `tryon-fixes` branch — it doesn't exist on `main` yet, so there is nothing to deploy against production until `tryon-fixes` merges.

## When `tryon-fixes` merges to `main`, the deploy is simple

One migration, purely additive and nullable:

```sql
ALTER TABLE tryon_jobs ADD COLUMN distractor_options JSON;
```

1. `git pull` on the VPS, into `/var/www/tryonu`.
2. `cd apps/api && source .venv/bin/activate && alembic upgrade head` — adds the one column. Nullable/additive: a running app with old code simply never reads it; nothing already there is touched. No backup strictly required for a change this small, but `pg_dump -F c tryonu_db > backup_$(date +%Y%m%d_%H%M).dump` first costs nothing and is good hygiene regardless.
3. `pm2 restart tryonu-api tryonu-worker`.
4. Smoke-check: create one real try-on job through a stylist pick, confirm it completes and `distractor_options` is non-null on the resulting `tryon_jobs` row (once `apps/web`'s own corresponding change — see the frontend work this session — is also deployed; until then every job just sends nothing and the backend falls back to its same-category guess, which is already safe).

No RLS lock-down, no 9-migration backlog, no risk category beyond "add one nullable column" — that whole analysis doesn't apply to real production. Nothing above has been run.
