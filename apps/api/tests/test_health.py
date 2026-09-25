

async def test_a_crash_answers_with_cors_headers_not_a_phantom_cors_error(client, monkeypatch):
    """Live incident: a 500 (a column missing because a migration hadn't
    run) reached the browser as "blocked by CORS policy", because
    Starlette's own error middleware sits outside the CORS middleware and
    its response carries no Access-Control-Allow-Origin. Handled inside,
    the error is legible as the 500 it is."""
    from app.main import app

    @app.get("/api/v1/_boom_for_test")
    async def boom():  # noqa: ANN202
        raise RuntimeError("something broke deep inside")

    resp = await client.get("/api/v1/_boom_for_test", headers={"Origin": "http://testserver"})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Something went wrong on our side. Please try again."
    assert resp.headers.get("access-control-allow-origin") == "http://testserver"
    assert "something broke deep inside" not in resp.text  # internals stay in the log


async def test_health_says_whether_the_database_has_this_code_s_migrations(client):
    """Deploying code without running its migrations breaks requests in
    ways that point anywhere but at the migration. /health answers it."""
    body = (await client.get("/health")).json()
    assert body["status"] == "ok"
    schema = body["schema"]
    assert schema["state"] in ("ok", "behind", "unknown")
    if schema["state"] == "behind":
        assert "alembic upgrade head" in schema["fix"]


async def test_startup_shouts_when_the_database_is_behind_the_code(capsys, monkeypatch):
    """Live: a deploy ran without its migration (alembic wasn't on PATH),
    and the first sign was a 500 in a browser an hour later."""
    import app.main as main

    async def behind():
        return {"state": "behind", "applied": "old", "expected": "new", "fix": "run: alembic upgrade head"}

    monkeypatch.setattr(main, "schema_status", behind)
    async with main.lifespan(main.app):
        pass
    printed = capsys.readouterr()
    logged = printed.out + printed.err
    assert "database_schema_behind_code" in logged
    assert "alembic upgrade head" in logged  # says what to do, not just that it's wrong


async def test_health_says_which_commit_is_running(client):
    """"Is the fix deployed?" has cost more time here than most bugs —
    a pull without a restart looks exactly like a restart without a pull."""
    body = (await client.get("/health")).json()
    assert "commit" in body
    commit = body["commit"]
    assert commit is None or (len(commit) == 7 and commit.isalnum())
