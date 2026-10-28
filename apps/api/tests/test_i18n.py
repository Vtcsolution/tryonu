"""The website in the visitor's language, only where English isn't widely
used, translated once and kept."""

from __future__ import annotations

from app.services import translate_service


def test_only_countries_that_prefer_their_own_language_get_it():
    assert translate_service.language_for("SA") == "ar" and translate_service.language_for("AE") == "ar"
    assert translate_service.language_for("JP") == "ja"
    assert translate_service.language_for("PK") == "en" and translate_service.language_for("IN") == "en"
    assert translate_service.language_for("GB") == "en" and translate_service.language_for(None) == "en"


async def test_the_locale_follows_the_visitors_country(client, monkeypatch):
    from app.api.v1.endpoints import i18n

    monkeypatch.setattr(i18n, "current_country", lambda: "SA")
    body = (await client.get("/api/v1/i18n/locale")).json()
    assert body["lang"] == "ar" and body["rtl"] is True and body["name"] == "العربية"
    monkeypatch.setattr(i18n, "current_country", lambda: "PK")
    assert (await client.get("/api/v1/i18n/locale")).json()["lang"] == "en"


async def test_text_is_translated_once_and_kept(client, monkeypatch):
    calls: list[list[str]] = []

    async def fake_ask(lang, texts):  # noqa: ANN001, ANN202
        calls.append(texts)
        return [f"[{lang}] {t}" for t in texts]

    monkeypatch.setattr(translate_service, "_ask", fake_ask)
    texts = ["Try on", "Ready looks", "Try on"]
    first = (await client.post("/api/v1/i18n/translate", json={"lang": "ja", "texts": texts})).json()
    assert first["texts"] == ["[ja] Try on", "[ja] Ready looks", "[ja] Try on"]
    assert calls == [["Try on", "Ready looks"]]  # each text once
    again = (await client.post("/api/v1/i18n/translate", json={"lang": "ja", "texts": ["Ready looks"]})).json()
    assert again["texts"] == ["[ja] Ready looks"] and len(calls) == 1  # kept: no second AI call
    refused = await client.post("/api/v1/i18n/translate", json={"lang": "xx", "texts": ["Hi"]})
    assert refused.status_code == 400
