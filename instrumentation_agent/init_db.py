"""Bootstrap Postgres metadata tables: ``uv run python -m instrumentation_agent.init_db``."""

from __future__ import annotations

from instrumentation_agent.utils.postgres import apply_meta_registry_ddl, ping_postgres


def main() -> None:
    print("Pinging Postgres…")
    ping_postgres()
    print("Applying meta registry DDL…")
    apply_meta_registry_ddl()
    print("Done.")


if __name__ == "__main__":
    main()
