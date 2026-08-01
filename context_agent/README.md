# Context Agent (catalog library)

Maintains the **living business context layer** in **Postgres** and exposes it as a
**library of two deterministic tools** for Instrumentation / Conversation / others.
There is **no Agno agent** in this package — other agents import the tools.

Parent overview: [`../README.md`](../README.md) · Table design: [`TABLES.md`](./TABLES.md)

## Role

```
Instrumentation writes meta_* → Postgres
Context logic publishes context_* → Postgres
        │
        ▼
  get_latest_context_items()   → meaning
  get_feature_meta(feature_id) → events + fields (+ objects)
        │
        ▼
  Imported by Conversation (or any Agno agent) as tools
```

## The 2 tools

| Tool | Purpose |
|------|---------|
| `get_latest_context_items` | Current `context_version` + `context_items` |
| `get_feature_meta(feature_id)` | `meta_objects` + `meta_events` + `meta_fields` |

```python
from context_agent import (
    get_context_catalog_tools,  # Agno Toolkit for another agent
    get_latest_context_items,   # direct call
    get_feature_meta,
)

# Inside Conversation / other agent:
tools = [get_context_catalog_tools()]

# Or without Agno:
bundle = get_latest_context_items()
meta = get_feature_meta("01_express_checkout")
```

`get_postgres_sql_tools()` is optional admin/debug only.

## Postgres tables

See [`TABLES.md`](./TABLES.md).

## Environment

Repo-root `.env`:

```bash
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
```

`SESSION_DATABASE_URL` is only needed if some other agent uses Agno sessions against Postgres.

## Setup

```bash
uv sync
uv run python context_agent/scripts/init_schema.py

# Optional health check service (no agent):
PYTHONPATH=context_agent/src uv run uvicorn context_agent.app:app --reload --port 8001
```

## Related

- [`TABLES.md`](./TABLES.md)
- [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- [`../conversation_agent/README.md`](../conversation_agent/README.md)
