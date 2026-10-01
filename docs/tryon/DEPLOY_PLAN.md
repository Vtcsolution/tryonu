# Production DB migration deploy plan — NOT executed, for review only

Production's Alembic revision is `164e48411da8` ("add product merchant fields"). The code's current head is `a1f6c3d8b254` (this branch's own `distractor_options` column) — **10 migrations behind**, not 9: the 9 that predate this session's `tryon-fixes` work, plus one this session added.

**Before running any of this, confirm whether it's actually needed**: check the commit the VPS is running (`pm2` env, or deploy notes, or `git log` on the VPS checkout) against what's in `main` right now. If the VPS is still on a commit from before the `placements`/`admin_audit_logs`/etc. models existed in code, the DB being behind is consistent and nothing is actually broken yet — only once the *deployed code* expects a column the DB doesn't have does this turn into a live bug. I don't have a way to check the VPS's deployed commit from here (no SSH, no public `/health` URL configured in this environment's `.env`) — I need that from you, or `app/main.py`'s `/health` endpoint returns `"commit": running_commit()`, so `curl https://<your-api-host>/health` would answer it directly, read-only, if you give me the host.

## The 10 pending migrations, in order, each with what it changes

| # | Revision | What it does | Risk |
|---|---|---|---|
| 1 | `183dc7670270` — add wardrobe item to tryon jobs | `ALTER TABLE tryon_jobs ADD COLUMN wardrobe_item_id` + FK to `wardrobe_items`, nullable | Low — additive, nullable |
| 2 | `5b1e8d2c9a47` — add admin audit logs | `CREATE TABLE admin_audit_logs` (new table) | Low — new table, nothing depends on it existing yet |
| 3 | `9c4f2a7d1e30` — add app settings | `CREATE TABLE app_settings` (new table) | Low — new table |
| 4 | `e7a3b91c5d62` — add page views | `CREATE TABLE page_views` (new table) | Low — new table |
| 5 | `a4d8c2e6f913` — add preferred categories | `ALTER TABLE user_preferences ADD COLUMN preferred_categories` (JSON, nullable) | Low — additive, nullable |
| 6 | `f1c8e42a7b03` — **lock down the Supabase public API** | Enables Postgres Row-Level-Security on **every table in the `public` schema**, then (only if an `anon` role exists, i.e. only on real Supabase) revokes all privileges on every table/sequence/function/schema from `anon`/`authenticated` | **The one to slow down on**, though lower-risk than it first looks. The app and worker connect as `postgres` (the table owner), which RLS doesn't restrict — so backend behavior should be unaffected by design. Checked now: `apps/web` has no `@supabase/supabase-js` dependency and no "supabase" string anywhere in `src/` — the frontend never talks to Supabase directly, only through this API. The one caveat migration 6 can't rule out from code alone: it touches **every** table in `public`, not just ones this project's own Alembic chain created — if Supabase itself or any manual work ever created a table there outside this history, it gets locked down too, worth a quick look at the Supabase dashboard's table list before running. `downgrade()` is available (disables RLS again) but deliberately does **not** restore the revoked grants — re-opening the API is a decision its own author said should never be a side effect of stepping back |
| 7 | `b7d4f019ca55` — add result placements | `ALTER TABLE tryon_results ADD COLUMN placements` (JSON, nullable) | Low — additive, nullable. **This is the one blocking `calibrate_distractor_rank.py` today.** |
| 8 | `c9a51e73b204` — add saved products | `CREATE TABLE saved_products` (new table) | Low — new table |
| 9 | `e4b8c1d90a37` — add job progress | `ALTER TABLE tryon_jobs ADD COLUMN progress` (string, nullable) | Low — additive, nullable |
| 10 | `a1f6c3d8b254` — add distractor_options *(this session, `tryon-fixes` branch)* | `ALTER TABLE tryon_jobs ADD COLUMN distractor_options` (JSON, nullable) | Low — additive, nullable |

9 of 10 are pure additive, nullable changes (new column or new table) — the lowest-risk category of migration; a running app with old code simply never reads the new column/table, and nothing already there is touched. Migration 6 (RLS lock-down) is the only one that changes *behavior* rather than *schema*, which is why it's flagged separately above.

## The plan, in order (do not execute without explicit go-ahead)

1. **Verify the VPS's deployed commit** against `main`'s current HEAD (see the open question above) — confirms whether the gap is actually live-impacting yet.
2. **`pg_dump` the production database** to a timestamped file, stored somewhere outside the VPS itself (your machine, S3/R2, wherever backups already go) — `pg_dump "$DATABASE_URL" -F c -f tryonu_prod_$(date +%Y%m%d_%H%M).dump`. Confirm the dump file's size/row counts look sane before proceeding (a 0-byte or truncated dump is worse than no backup — it creates false confidence).
3. **Grep `apps/web` for direct Supabase client usage** (migration 6's own precondition — see above). If anything uses the anon key directly, migration 6 needs a policy added for that path before it runs, not after.
4. **Run `alembic upgrade head`** against production (requires `ALLOW_PROD_WRITES=true` once `app/core/db_safety.py`'s guard is wired into whatever runs this — see below). Watch for errors on migration 6 specifically; the other 9 are mechanically safe.
5. **Deploy the new code** (the commit that expects these columns/tables) — `git pull` + `pm2 restart tryonu-api tryonu-worker`, this project's existing deploy mechanism (no CI/CD, confirmed earlier this session).
6. **Smoke-check**: hit `/health`, create one real try-on job, confirm `tryon_results.placements` gets written (the exact column that's missing today), confirm the admin panel's settings/audit-log pages (if already deployed in the frontend) don't 500.

Nothing above has been run. Waiting for your go-ahead on step 1 (the commit check) before anything else is worth deciding.
