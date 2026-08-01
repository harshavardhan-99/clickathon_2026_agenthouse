"""Postgres engine + metadata DDL bootstrap."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, text

from instrumentation_agent.settings import get_settings

_SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "postgres_meta_registry.sql"

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def apply_meta_registry_ddl(engine: Engine | None = None) -> None:
    """Apply ``meta_features`` + ``meta_events`` DDL (idempotent CREATE)."""
    eng = engine or get_engine()
    ddl = _SQL_PATH.read_text(encoding="utf-8")
    raw = eng.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(ddl)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def ping_postgres(engine: Engine | None = None) -> bool:
    eng = engine or get_engine()
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
