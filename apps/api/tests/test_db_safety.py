"""db_safety.assert_safe_to_write(): the guard a dev-only write script
should call before its first write. Matches on ENV=production (the
settings field this app already uses to distinguish environments), not a
guessed database host -- an earlier version matched a specific Supabase
host that turned out not to be production at all (see memory
production_db_is_local_postgres_on_vps)."""

from __future__ import annotations

import pytest

from app.core.db_safety import ProductionWriteBlocked, assert_safe_to_write, is_production_environment


def test_recognises_the_production_environment():
    assert is_production_environment("production")


def test_development_and_staging_are_not_production():
    assert not is_production_environment("development")
    assert not is_production_environment("staging")


def test_refuses_to_write_in_production_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_PROD_WRITES", raising=False)
    with pytest.raises(ProductionWriteBlocked):
        assert_safe_to_write("production")


def test_allows_the_write_when_explicitly_opted_in(monkeypatch):
    monkeypatch.setenv("ALLOW_PROD_WRITES", "true")
    assert_safe_to_write("production")  # must not raise


def test_a_non_production_environment_never_needs_the_opt_in(monkeypatch):
    monkeypatch.delenv("ALLOW_PROD_WRITES", raising=False)
    assert_safe_to_write("development")  # must not raise
