# Instrumentation Agent

Turns a feature **`spec.md` + `events.ndjson`** into ClickHouse tables + Postgres metadata.

Parent overview: [`../README.md`](../README.md)

## Package layout

```
instrumentation_agent/
├── routes/                 # thin FastAPI routers
│   ├── health.py
│   └── instrumentation.py
├── interfaces/             # service entrypoints (not fat __init__)
│   ├── health.py
│   └── instrumentation.py
├── models/
│   ├── schemas.py          # Pydantic request/response
│   └── domain.py           # dataclasses
├── db/
│   ├── connection.py
│   ├── meta_features.py
│   └── meta_events.py
├── utils/                  # concrete helper modules only
│   ├── profiler.py
│   ├── paths.py
│   ├── clickhouse.py       # SQLGlot-validated CH SQL
│   └── serialize.py
├── tools/instrumentation.py
├── sql/
├── settings.py
└── init_db.py
```

`__init__.py` files stay thin (re-exports or empty). Import from concrete modules.
Thin host: `app/main.py` mounts `instrumentation_agent.routes`.

## Layering

| Layer | Responsibility |
|-------|----------------|
| **routes** | HTTP only; call `interfaces` |
| **interfaces** | Orchestration (`instrument_feature`, `get_registry`, `health_check`) |
| **models** | Pydantic requests/responses + domain dataclasses |
| **db** | Table-scoped CRUD classes only |
| **utils** | Shared helpers; ClickHouse DDL/queries validated with **SQLGlot** |

## API

| Method | Path | Interface |
|--------|------|-----------|
| `GET` | `/health` | `health_check()` |
| `GET` | `/v1/registry/{feature_id}` | `get_registry()` |
| `POST` | `/v1/instrument` | `instrument_feature()` |

```bash
uv run python -m instrumentation_agent.init_db
uv run uvicorn app.main:app --reload --port 8000
```
