"""Tests for `app.services.sql_lookup` (DB stubs this round).

These tests verify the stub behavior: when DB env vars are not set,
the functions return None / empty without raising. When DB env vars
ARE set, they raise `DatabaseNotConfigured` (signaling the connection
needs to be wired in Phase 4).
"""

from __future__ import annotations

import pytest

from app.services import sql_lookup


@pytest.fixture(autouse=True)
def _clear_db_env(monkeypatch):
    for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)


def test_get_product_by_name_or_id_returns_none_when_unconfigured():
    assert sql_lookup.get_product_by_name_or_id("10 GB data pack", "omantel") is None


def test_get_profile_id_returns_none_when_unconfigured():
    assert sql_lookup.get_profile_id("ACCOUNT_TYPE") is None


def test_get_action_id_returns_none_when_unconfigured():
    assert sql_lookup.get_action_id("Send Promotion") is None


def test_get_bonus_details_returns_none_when_unconfigured():
    assert sql_lookup.get_bonus_details("Recharge", "SUM") is None


def test_db_not_configured_check():
    assert sql_lookup._db_configured() is False
    # The test fixture cleared env; verify by reading again
    import os
    assert not os.environ.get("DB_HOST")


def test_get_product_by_name_or_id_returns_none_when_configured_but_unreachable(monkeypatch):
    """When DB env vars are set but the DB is unreachable, return None (not raise)."""
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    # Don't actually try to connect in CI — patch _connect to raise.
    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: (_ for _ in ()).throw(RuntimeError("connection failed")))
    result = _sql.get_product_by_name_or_id("anything", "omantel")
    assert result is None


def test_get_profile_id_returns_none_when_configured_but_unreachable(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: (_ for _ in ()).throw(RuntimeError("connection failed")))
    result = _sql.get_profile_id("ACCOUNT_TYPE")
    assert result is None


def test_get_action_id_returns_none_when_configured_but_unreachable(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: (_ for _ in ()).throw(RuntimeError("connection failed")))
    result = _sql.get_action_id("Send Promotion")
    assert result is None


def test_get_bonus_details_returns_none_when_configured_but_unreachable(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: (_ for _ in ()).throw(RuntimeError("connection failed")))
    result = _sql.get_bonus_details("Recharge", "SUM")
    assert result is None

class _FakeCursorEndToEnd:
    def __init__(self, rows):
        self._rows = rows
        self.last_sql = None
        self.last_params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None


class _FakeConnEndToEnd:
    def __init__(self, rows):
        self._cursor = _FakeCursorEndToEnd(rows)

    def cursor(self):
        return self._cursor


def test_get_profile_id_real_query_returns_id(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    fake = _FakeConnEndToEnd([(42,)])
    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: fake)
    result = _sql.get_profile_id("ACCOUNT_TYPE")
    assert result == 42
    assert "RE_BUSINESS_KPIS" in fake._cursor.last_sql


def test_get_action_id_real_query_returns_id(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    fake = _FakeConnEndToEnd([(75,)])
    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: fake)
    result = _sql.get_action_id("Send Promotion")
    assert result == 75
    assert "RE_ACTION_INFO" in fake._cursor.last_sql


def test_get_product_by_name_or_id_real_query_returns_id(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    fake = _FakeConnEndToEnd([("P123",)])
    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: fake)
    result = _sql.get_product_by_name_or_id("10 GB Flash", "omantel")
    assert result == "P123"
    assert "PROD_PRODUCT_MASTER" in fake._cursor.last_sql


def test_get_bonus_details_real_query_returns_dict(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    fake = _FakeConnEndToEnd([("PROFILE_X", "TX_DATE_Y")])
    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: fake)
    result = _sql.get_bonus_details("Recharge", "SUM")
    assert result == {"profile_name": "PROFILE_X", "transaction_date": "TX_DATE_Y"}
    assert "BONUS_RULE_KPI_DETAILS" in fake._cursor.last_sql


def test_get_bonus_details_returns_none_when_no_row(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.10.24")
    monkeypatch.setenv("DB_NAME", "Magik_3.0_Demo_Upgrade")
    monkeypatch.setenv("DB_USER", "magikuser")
    monkeypatch.setenv("DB_PASSWORD", "test")

    fake = _FakeConnEndToEnd([])
    from app.services import sql_lookup as _sql
    monkeypatch.setattr(_sql, "_connect", lambda: fake)
    result = _sql.get_bonus_details("Unknown", "SUM")
    assert result is None
