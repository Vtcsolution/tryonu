"""lock down the Supabase public API over our tables

Supabase puts PostgREST in front of every table in `public`, reachable
with the project URL and the anon key. Our tables come from Alembic, so
they have no RLS policies — and with none, anon could read and write
users.hashed_password, the token hashes, photo keys and payments
(Supabase's own advisory: rls_disabled_in_public,
sensitive_columns_exposed).

Turning RLS on with no policies closes that: Postgres does not apply RLS
to a table's owner, and the API and worker connect as `postgres`, which
owns these tables — so they are unaffected. Nothing we run uses
supabase-js or the REST API.

Same statements as scripts/supabase_lockdown.sql, so a deploy that runs
`alembic upgrade head` applies them too. SQLite (tests, local dev) has no
such concept and is skipped.

Revision ID: f1c8e42a7b03
Revises: a4d8c2e6f913
Create Date: 2026-09-23
"""

from alembic import op

revision = "f1c8e42a7b03"
down_revision = "a4d8c2e6f913"
branch_labels = None
depends_on = None

_ENABLE_RLS = """
do $$
declare t record;
begin
  for t in select schemaname, tablename from pg_tables where schemaname = 'public'
  loop
    execute format('alter table %I.%I enable row level security', t.schemaname, t.tablename);
  end loop;
end $$;
"""

_REVOKE = """
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;
revoke usage on schema public from anon, authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke all on functions from anon, authenticated;
"""

_DISABLE_RLS = """
do $$
declare t record;
begin
  for t in select schemaname, tablename from pg_tables where schemaname = 'public'
  loop
    execute format('alter table %I.%I disable row level security', t.schemaname, t.tablename);
  end loop;
end $$;
"""


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _postgres():
        return
    op.execute(_ENABLE_RLS)
    # the anon/authenticated roles only exist on Supabase; on a plain
    # Postgres (docker-compose, CI) there is nothing to revoke
    if op.get_bind().exec_driver_sql("select 1 from pg_roles where rolname = 'anon'").first():
        op.execute(_REVOKE)


def downgrade() -> None:
    # Deliberately does not hand the grants back: re-opening the public API
    # should be a decision someone makes on purpose, not a side effect of
    # stepping a migration back. See the note at the end of
    # scripts/supabase_lockdown.sql.
    if _postgres():
        op.execute(_DISABLE_RLS)
