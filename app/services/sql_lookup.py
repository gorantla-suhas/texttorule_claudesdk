"""Database lookups — real DB connection (Phase 4) with stub fallback.

These functions are called by `app/tools/lookup_bonus.py` (benefit
SQL → product_id) and `app/tools/parse_intermediate_to_final.py`
(final-JSON SQL → profile_id, action_id, bonus_details).

This round: stubbed. Each function returns `None` (or empty list)
when the DB is not reachable, with a logged warning. The pipeline
remains exercisable; only the resolved IDs end up empty.

The SQL queries (from `data/sdk_context/db_details`) are documented
in each function's docstring.

Connection configuration (env vars):

    DB_HOST       default "10.0.10.24"
    DB_NAME       default "Magik_3.0_Demo_Upgrade"
    DB_USER       default "magikuser"
    DB_PASSWORD   required, no default (never commit a default)
    DB_PORT       default <driver-specific>

Driver library: the connection is implemented in `_connect()`.
Default: `pyodbc` for Microsoft SQL Server / Sybase. If the actual
DB is different, swap `_connect()` to use `pymysql`, `psycopg2`, etc.

Until the connection is wired, all four functions return `None` /
empty list and emit a `DatabaseNotConfigured` warning. The pipeline
treats missing IDs as described in `final-rule-json.md` (hard error
for profile / action / product_id-when-benefits; soft for bonus).
"""

from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class DatabaseNotConfigured(RuntimeError):
    """Raised when DB env vars are missing or connection fails."""


def _db_configured() -> bool:
    """True if all required DB env vars are set."""

    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    return all(os.environ.get(k) for k in required)


def _connect():  # pragma: no cover — DB connection wraps external driver
    """Open a DB connection.

    Default driver: pyodbc (ODBC; works with MS SQL Server / Sybase
    via the appropriate ODBC driver). If your SQL is MySQL or
    PostgreSQL, install the matching driver and replace this
    function.

    Required env vars:
        DB_HOST       (default "10.0.10.24")
        DB_NAME       (default "Magik_3.0_Demo_Upgrade")
        DB_USER       (default "magikuser")
        DB_PASSWORD   (no default; must be set)

    Returns a connection with a `.cursor()` method that supports
    context manager: `with conn.cursor() as cur: cur.execute(sql)`.
    """

    import importlib

    host = os.environ.get("DB_HOST", "10.0.10.24")
    name = os.environ.get("DB_NAME", "Magik_3.0_Demo_Upgrade")
    user = os.environ.get("DB_USER", "magikuser")
    password = os.environ["DB_PASSWORD"]
    driver = os.environ.get("DB_DRIVER", "ODBC Driver 17 for SQL Server")

    pyodbc_spec = importlib.util.find_spec("pyodbc")
    if pyodbc_spec is None:
        raise DatabaseNotConfigured(
            "pyodbc not installed. Install with `pip install pyodbc` "
            "or set DB_DRIVER to a driver available via the chosen "
            "Python DB library."
        )

    import pyodbc  # type: ignore[import-not-found]

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={host};"
        f"DATABASE={name};"
        f"UID={user};"
        f"PWD={password};"
    )
    return pyodbc.connect(conn_str, autocommit=True)


# ---------------------------------------------------------------------------
# Benefit SQL — resolve product_id from free-text product name
# ---------------------------------------------------------------------------


def get_product_by_name_or_id(query: str, client: str) -> str | None:
    """Resolve a product_id for the benefit / bonus product.

    SQL (from `data/sdk_context/db_details`):

        SELECT
            pm.ID,
            pm.PRODUCT_NAME,
            pm.UPC_PRODUCT,
            pt.NAME AS PRODUCT_TYPE,
            pg.NAME AS PRODUCT_GROUP,
            vt.NAME AS VALIDITY_TYPE,
            pm.VALIDITY,
            pm.PRICE,
            pm.CREATE_DATE
        FROM PROD_PRODUCT_MASTER pm
        LEFT JOIN PROD_PRODUCT_TYPE pt ON pm.PRODUCT_TYPE = pt.ID
        LEFT JOIN PROD_PRODUCT_GROUP pg ON pm.PRODUCT_GROUP = pg.ID
        LEFT JOIN PROD_VALIDITY_TYPES vt ON pm.VALIDITY_TYPE = vt.ID;

    Returns the resolved `product_id` (string) on match, `None` on
    miss, raises `DatabaseNotConfigured` if DB env vars missing or
    connection fails.

    Matching strategy: LIKE match on `PRODUCT_NAME` or exact match on
    `UPC_PRODUCT`. The first hit wins.
    """

    if not _db_configured():
        log.warning("DB not configured; get_product_by_name_or_id returns None for %r", query)
        return None

    sql = (
        "SELECT TOP 1 pm.ID "
        "FROM PROD_PRODUCT_MASTER pm "
        "WHERE pm.PRODUCT_NAME LIKE ? OR pm.UPC_PRODUCT = ?"
    )
    pattern = f"%{query.strip()}%"
    try:
        with _connect().cursor() as cur:
            cur.execute(sql, (pattern, query.strip()))
            row = cur.fetchone()
            if row is None:
                return None
            return str(row[0])
    except Exception as exc:
        log.error("get_product_by_name_or_id failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Final-JSON SQL — resolve profile_id, action_id, bonus_details
# ---------------------------------------------------------------------------


def get_profile_id(profile_name: str) -> int | None:
    """Resolve a profile's DB ID by its KPI name.

    SQL (from `data/sdk_context/db_details`):

        SELECT rbk.ID AS ID, PROFILE_NAME, rdt.NAME AS DATA_TYPE
        FROM RE_BUSINESS_KPIS rbk
        JOIN RE_DATA_TYPES rdt ON rbk.DATA_TYPE = rdt.ID

    Returns the resolved `id` (int) on match, `None` on miss. The
    `DATA_TYPE` is read alongside for `validate_intermediate_rule`'s
    operator-validity check (Phase 5).
    """

    if not _db_configured():
        log.warning("DB not configured; get_profile_id returns None for %r", profile_name)
        return None

    sql = (
        "SELECT TOP 1 rbk.ID "
        "FROM RE_BUSINESS_KPIS rbk "
        "WHERE rbk.PROFILE_NAME = ?"
    )
    try:
        with _connect().cursor() as cur:
            cur.execute(sql, (profile_name.strip(),))
            row = cur.fetchone()
            if row is None:
                return None
            return int(row[0])
    except Exception as exc:
        log.error("get_profile_id failed: %s", exc)
        return None


def get_action_id(action_name: str) -> int | None:
    """Resolve an action's DB ID by its name.

    SQL (from `data/sdk_context/db_details`):

        SELECT ID, NAME FROM RE_ACTION_INFO

    Returns the resolved `id` (int) on match, `None` on miss.
    """

    if not _db_configured():
        log.warning("DB not configured; get_action_id returns None for %r", action_name)
        return None

    sql = (
        "SELECT TOP 1 ID FROM RE_ACTION_INFO WHERE NAME = ?"
    )
    try:
        with _connect().cursor() as cur:
            cur.execute(sql, (action_name.strip(),))
            row = cur.fetchone()
            if row is None:
                return None
            return int(row[0])
    except Exception as exc:
        log.error("get_action_id failed: %s", exc)
        return None


def get_bonus_details(action_type: str, aggregation: str) -> dict[str, Any] | None:
    """Resolve bonus profile_name + transaction_date_profile.

    SQL (from `data/sdk_context/db_details`):

        SELECT ACTION_TYPE, `FUNCTION`, PROFILE_NAME,
               TRANSACTION_DATE_PROFILE
        FROM BONUS_RULE_KPI_DETAILS brkd
        JOIN BONUS_RULE_KPI_MASTER brkm
          ON brkd.ACTION_TYPE_ID = brkm.ID

    Returns a dict with keys `profile_name` and
    `transaction_date_profile` on match, `None` on miss. Soft failure
    if not found (final-JSON bonus block keeps the empty fields per
    `final-rule-json.md`).
    """

    if not _db_configured():
        log.warning(
            "DB not configured; get_bonus_details returns None for %r/%r",
            action_type, aggregation,
        )
        return None

    sql = (
        "SELECT TOP 1 brkd.PROFILE_NAME, brkd.TRANSACTION_DATE_PROFILE "
        "FROM BONUS_RULE_KPI_DETAILS brkd "
        "JOIN BONUS_RULE_KPI_MASTER brkm "
        "  ON brkd.ACTION_TYPE_ID = brkm.ID "
        "WHERE brkm.ACTION_TYPE = ? AND brkd.`FUNCTION` = ?"
    )
    try:
        with _connect().cursor() as cur:
            cur.execute(sql, (action_type.strip(), aggregation.strip().upper()))
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "profile_name": str(row[0] or ""),
                "transaction_date": str(row[1] or ""),
            }
    except Exception as exc:
        log.error("get_bonus_details failed: %s", exc)
        return None


__all__ = [
    "DatabaseNotConfigured",
    "get_product_by_name_or_id",
    "get_profile_id",
    "get_action_id",
    "get_bonus_details",
]