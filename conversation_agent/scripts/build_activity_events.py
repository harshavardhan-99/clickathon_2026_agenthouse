#!/usr/bin/env python3
"""Create atlys.activity_events and backfill from existing per-event tables.

Skips funnel_events (denormalized subset of the funnel tables) to avoid duplicates.

Usage:
    uv run python conversation_agent/scripts/build_activity_events.py
    uv run python conversation_agent/scripts/build_activity_events.py --sample 5000
    uv run python conversation_agent/scripts/build_activity_events.py --drop
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as script without install path quirks
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from conversation_agent import config

# Minimal SAS envelope (everything else → event_info JSON)
ENVELOPE = frozenset(
    {
        "id",
        "timestamp",
        "user_id",
        "application_id",
        "device_type",
        "os",
        "geoip_country_code",
        "destination",
    }
)

# Source fact tables (not funnel_events)
SOURCE_TABLES = (
    "destination_card_clicked",
    "application_started",
    "document_uploaded",
    "purchase_completed",
    "search_typed",
    "landing_page_scrolled",
    "auth_completed",
    "pay_now_clicked",
)


def _client():
    import clickhouse_connect

    if not config.CLICKHOUSE_HOST or not config.CLICKHOUSE_USER:
        raise RuntimeError("Set CLICKHOUSE_HOST and CLICKHOUSE_USER in .env")
    return clickhouse_connect.get_client(
        host=config.CLICKHOUSE_HOST,
        port=config.CLICKHOUSE_PORT,
        username=config.CLICKHOUSE_USER,
        password=config.CLICKHOUSE_PASSWORD,
        database=config.CLICKHOUSE_DATABASE,
        secure=config.CLICKHOUSE_SECURE,
        verify=config.CLICKHOUSE_VERIFY,
        connect_timeout=60,
        send_receive_timeout=600,
    )


def _ddl(fqn: str) -> str:
    return f"""
CREATE TABLE IF NOT EXISTS {fqn}
(
    id String,
    timestamp DateTime,
    event_name LowCardinality(String),
    user_id String,
    application_id Nullable(String),
    device_type LowCardinality(Nullable(String)),
    os LowCardinality(Nullable(String)),
    geoip_country_code LowCardinality(Nullable(String)),
    destination LowCardinality(Nullable(String)),
    event_info String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event_name, user_id, timestamp)
SETTINGS index_granularity = 8192
""".strip()


def _table_columns(client, database: str, table: str) -> list[str]:
    rows = client.query(f"DESCRIBE TABLE `{database}`.`{table}`").result_rows
    return [r[0] for r in rows]


def _event_info_sql(columns: list[str]) -> str:
    extras = [c for c in columns if c not in ENVELOPE]
    if not extras:
        return "toJSONString(map())"
    # Stringify all payload fields; drop null/empty in mapFilter
    pairs = ", ".join(f"'{c}', ifNull(toString(`{c}`), '')" for c in extras)
    return (
        "toJSONString(mapFilter((k, v) -> (v != '' AND v != 'NULL'), "
        f"map({pairs})))"
    )


def _insert_sql(
    *,
    database: str,
    fqn: str,
    table: str,
    columns: list[str],
    sample: int | None,
) -> str:
    info = _event_info_sql(columns)
    has_id = "id" in columns
    id_expr = "toString(id)" if has_id else f"generateUUIDv4()"
    # Ensure envelope cols exist
    for col in (
        "timestamp",
        "user_id",
        "application_id",
        "device_type",
        "os",
        "geoip_country_code",
        "destination",
    ):
        if col not in columns:
            raise RuntimeError(f"{table} missing required column {col}")

    limit = f"\nLIMIT {int(sample)}" if sample and sample > 0 else ""
    return f"""
INSERT INTO {fqn}
(
    id, timestamp, event_name, user_id, application_id,
    device_type, os, geoip_country_code, destination, event_info
)
SELECT
    {id_expr} AS id,
    timestamp,
    '{table}' AS event_name,
    user_id,
    application_id,
    device_type,
    os,
    geoip_country_code,
    destination,
    {info} AS event_info
FROM `{database}`.`{table}`
{limit}
""".strip()


def build(*, drop: bool = False, sample: int | None = None) -> dict:
    database = config.CLICKHOUSE_DATABASE
    table_name = config.CLICKHOUSE_ACTIVITY_TABLE or "activity_events"
    fqn = config.activity_table_fqn()

    client = _client()
    try:
        if drop:
            client.command(f"DROP TABLE IF EXISTS {fqn}")
            print(f"Dropped {fqn}")

        client.command(_ddl(fqn))
        print(f"Ensured {fqn}")

        # Fresh fill: truncate then insert (safer than drop on Cloud permissions)
        client.command(f"TRUNCATE TABLE IF EXISTS {fqn}")
        print(f"Truncated {fqn}")

        totals: dict[str, int] = {}
        for src in SOURCE_TABLES:
            cols = _table_columns(client, database, src)
            sql = _insert_sql(
                database=database,
                fqn=fqn,
                table=src,
                columns=cols,
                sample=sample,
            )
            print(f"Inserting from {src}…")
            client.command(sql)
            # count for this event_name
            n = client.query(
                f"SELECT count() FROM {fqn} WHERE event_name = {{n:String}}",
                parameters={"n": src},
            ).first_item
            count = int(n["count()"] if isinstance(n, dict) else n)
            totals[src] = count
            print(f"  → {count:,} rows")

        total = client.query(f"SELECT count() FROM {fqn}").first_item
        total_n = int(total["count()"] if isinstance(total, dict) else total)
        return {
            "table": fqn,
            "sample_per_table": sample,
            "by_event": totals,
            "total_rows": total_n,
        }
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build SAS activity_events from existing ClickHouse event tables"
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="DROP TABLE before CREATE (default: CREATE IF NOT EXISTS + TRUNCATE)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Limit rows per source table (for a quick sample load)",
    )
    args = parser.parse_args()
    result = build(drop=args.drop, sample=args.sample)
    print(result)


if __name__ == "__main__":
    main()
