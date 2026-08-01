# Instrumentation Agent

Turns a feature **`spec.md` + `events.ndjson`** into production **ClickHouse** schemas (and load), and writes a **queryable metadata registry to Postgres**.

Parent overview: [`../README.md`](../README.md)

## Package layout

```
instrumentation_agent/
├── settings.py
├── init_db.py
├── routes/           # FastAPI routers (health, instrument, registry)
├── tools/            # Agno InstrumentationTools
├── interfaces/       # Pydantic request/response schemas
├── models/           # EventProfile, FeatureProfile, FeaturePaths
├── utils/            # pipeline, profiler, postgres, clickhouse, registry
└── sql/              # postgres_meta_registry.sql
```

Thin host: `app/main.py` mounts `instrumentation_agent.routes.api_router`.

## Flow

```
POST /v1/instrument { feature_id }
        │
        ▼
utils.profiler → utils.clickhouse → utils.registry (Postgres)
```

## API

| Method | Path | Behavior |
|--------|------|----------|
| `GET` | `/health` | Postgres + ClickHouse ping |
| `GET` | `/v1/registry/{feature_id}` | Read metadata |
| `POST` | `/v1/instrument` | Run full pipeline |

```bash
uv run python -m instrumentation_agent.init_db
uv run uvicorn app.main:app --reload --port 8000
```

## Related

- [`../conversation_agent/README.md`](../conversation_agent/README.md)
- [`../context_agent/README.md`](../context_agent/README.md)
