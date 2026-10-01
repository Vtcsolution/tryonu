"""db_safety.assert_safe_to_write(): the guard a dev-only write script
should call before its first write, so a .env accidentally (or
deliberately, for read-only work) pointed at production can't also let a
write slip through unnoticed."""

from __future__ import annotations

import pytest

from app.core.db_safety import PRODUCTION_DB_HOST, ProductionWriteBlocked, assert_safe_to_write, is_production_database


def test_recognises_the_production_host_regardless_of_credentials_or_driver():
    url = f"postgresql+asyncpg://someuser:somepass@{PRODUCTION_DB_HOST}:5432/postgres"
    assert is_production_database(url)


def test_a_different_host_is_not_production():
    assert not is_production_database("postgresql://user:pass@localhost:5432/tryonu_dev")
    assert not is_production_database("sqlite+aiosqlite:///./tryonu.db")


def test_refuses_to_write_against_production_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_PROD_WRITES", raising=False)
    url = f"postgresql://user:pass@{PRODUCTION_DB_HOST}/postgres"
    with pytest.raises(ProductionWriteBlocked):
        assert_safe_to_write(url)


def test_allows_the_write_when_explicitly_opted_in(monkeypatch):
    monkeypatch.setenv("ALLOW_PROD_WRITES", "true")
    url = f"postgresql://user:pass@{PRODUCTION_DB_HOST}/postgres"
    assert_safe_to_write(url)  # must not raise


def test_a_non_production_database_never_needs_the_opt_in(monkeypatch):
    monkeypatch.delenv("ALLOW_PROD_WRITES", raising=False)
    assert_safe_to_write("postgresql://user:pass@localhost:5432/tryonu_dev")  # must not raise
