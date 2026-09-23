-- Close Supabase's public API over our tables.
--
-- Why this is needed: Supabase hosts our Postgres, but it also puts a REST
-- API (PostgREST) in front of every table in `public`, reachable by anyone
-- who has the project URL and the anon key — which ships in any browser
-- that ever talks to Supabase. Our tables were created by Alembic, so they
-- have no Row-Level Security policies, and with none, PostgREST's anon role
-- could read and write everything: users.hashed_password and email, the
-- refresh/password-reset/verification token hashes, customers' photo keys,
-- payments. That is what the "rls_disabled_in_public" and
-- "sensitive_columns_exposed" advisories are about.
--
-- Why it is safe: nothing we run uses Supabase's REST API or supabase-js.
-- The API and worker connect straight to Postgres as the `postgres` role,
-- which owns these tables, and Postgres does not apply RLS to a table's
-- owner (we deliberately do NOT use FORCE ROW LEVEL SECURITY). So the app
-- keeps full access and the public API is left with nothing.
--
-- Run it in the Supabase dashboard: SQL Editor -> New query -> paste ->
-- Run. It is idempotent; run it again after adding tables.

begin;

-- 1. RLS on, no policies: every role that isn't the owner sees no rows.
do $$
declare t record;
begin
  for t in select schemaname, tablename from pg_tables where schemaname = 'public'
  loop
    execute format('alter table %I.%I enable row level security', t.schemaname, t.tablename);
  end loop;
end $$;

-- 2. Take back the grants Supabase hands the public API's roles. RLS alone
--    would stop the rows; this stops them reaching the tables at all.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;
revoke usage on schema public from anon, authenticated;

-- 3. And for tables a future migration creates.
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke all on functions from anon, authenticated;

commit;

-- Check it worked: this should return no rows.
select tablename as "table still without RLS"
from pg_tables
where schemaname = 'public'
  and not rowsecurity
order by tablename;

-- And this should also return no rows.
select table_name, grantee, privilege_type
from information_schema.role_table_grants
where table_schema = 'public' and grantee in ('anon', 'authenticated')
order by table_name, grantee;

-- To undo (only if you ever decide to use supabase-js from the browser —
-- you would then need real RLS policies before granting anything back):
--   grant usage on schema public to anon, authenticated;
