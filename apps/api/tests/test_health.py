

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
