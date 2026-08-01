"""ClickHouse SQL built and validated with SQLGlot (clickhouse dialect)."""

from __future__ import annotations

from typing import Any

import clickhouse_connect
import sqlglot
from clickhouse_connect.driver.client import Client
from sqlglot import exp

from instrumentation_agent.models.domain import EventProfile
from instrumentation_agent.settings import Settings, get_settings

_PREFERRED_ORDER = ("timestamp", "device_type", "destination", "user_id", "application_id")
_DIALECT = "clickhouse"


def get_client(settings: Settings | None = None) -> Client:
    cfg = settings or get_settings()
    return clickhouse_connect.get_client(
        host=cfg.clickhouse_host,
        port=cfg.clickhouse_port,
        username=cfg.clickhouse_user,
        password=cfg.clickhouse_password,
        database=cfg.clickhouse_database,
        secure=cfg.clickhouse_secure,
    )


def validate_sql(sql: str) -> exp.Expression:
    """Parse SQL as ClickHouse (raises if invalid)."""
    return sqlglot.parse_one(sql, read=_DIALECT)


def execute_sql(client: Client, sql: str) -> None:
    """Validate with SQLGlot then run a ClickHouse command (original SQL text)."""
    validate_sql(sql)
    client.command(sql)


def query_sql(client: Client, sql: str) -> Any:
    """Validate with SQLGlot then run a ClickHouse query (original SQL text)."""
    validate_sql(sql)
    return client.query(sql)


def ping_clickhouse(settings: Settings | None = None) -> bool:
    client = get_client(settings)
    try:
        query_sql(client, "SELECT 1")
    finally:
        client.close()
    return True


def _order_by_sql(columns: dict[str, str]) -> str:
    keys = [c for c in _PREFERRED_ORDER if c in columns]
    if not keys:
        first = next(iter(columns), None)
        return f"({first})" if first else "(tuple())"
    parts: list[str] = []
    for key in keys:
        if key == "timestamp":
            parts.append("toDate(timestamp)")
        else:
            parts.append(key)
    return "(" + ", ".join(parts) + ")"


def build_drop_table_sql(database: str, table: str) -> str:
    sql = f"DROP TABLE IF EXISTS `{database}`.`{table}`"
    tree = validate_sql(sql)
    if not isinstance(tree, exp.Drop):
        raise ValueError(f"expected DROP statement, got {type(tree)}")
    return sql


def build_create_table_sql(profile: EventProfile, database: str) -> str:
    cols = profile.columns
    if not cols:
        raise ValueError(f"no columns inferred for event {profile.event_name}")
    col_defs = ",\n    ".join(f"`{name}` {ch_type}" for name, ch_type in cols.items())
    order_by = _order_by_sql(cols)
    partition = "PARTITION BY toYYYYMM(timestamp)" if "timestamp" in cols else ""
    sql = f"""
CREATE TABLE `{database}`.`{profile.ch_table}`
(
    {col_defs}
)
ENGINE = MergeTree
{partition}
ORDER BY {order_by}
""".strip()
    tree = validate_sql(sql)
    if not isinstance(tree, exp.Create):
        raise ValueError(f"expected CREATE statement, got {type(tree)}")
    return sql


def _normalize_value(value: Any, ch_type: str) -> Any:
    if value is None:
        if ch_type.startswith("LowCardinality") or ch_type == "String":
            return ""
        if ch_type == "Bool":
            return False
        if ch_type.startswith("Int") or ch_type.startswith("Float"):
            return 0
        if ch_type.startswith("DateTime"):
            return "1970-01-01 00:00:00.000"
        return ""
    if ch_type.startswith("DateTime") and isinstance(value, str):
        return value.replace("Z", "").replace("T", " ")
    return value


def apply_event_table(
    profile: EventProfile,
    *,
    client: Client | None = None,
    settings: Settings | None = None,
    recreate: bool = True,
) -> int:
    """DROP+CREATE (SQLGlot-validated) then bulk INSERT rows."""
    cfg = settings or get_settings()
    own_client = client is None
    ch = client or get_client(cfg)
    try:
        if recreate:
            execute_sql(ch, build_drop_table_sql(cfg.clickhouse_database, profile.ch_table))
        execute_sql(ch, build_create_table_sql(profile, cfg.clickhouse_database))
        col_names = list(profile.columns.keys())
        data = [
            [_normalize_value(row.get(c), profile.columns[c]) for c in col_names]
            for row in profile.rows
        ]
        if data:
            ch.insert(
                profile.ch_table,
                data,
                column_names=col_names,
                database=cfg.clickhouse_database,
            )
        return len(data)
    finally:
        if own_client:
            ch.close()
