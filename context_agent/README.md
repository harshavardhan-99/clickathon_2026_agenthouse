# Context Agent (catalog library)

Maintains the **living business context layer** in **Postgres** and exposes it as a
**library of two deterministic tools** for Instrumentation / Conversation / others.
There is **no Agno agent** in this package — other agents import the tools.

Parent overview: [`../README.md`](../README.md) · Table design: [`TABLES.md`](./TABLES.md)

## Role

```
Instrumentation writes meta_features / meta_events → Postgres
Context publishes context_versions / context_items → Postgres
        │
        ▼
  get_latest_context_items()   → meaning (context_*)
  get_feature_meta(feature_id) → journey + shared activity table + event_info columns
  publish_context_version(...) → new context version (copy-forward + deltas)
        │
        ▼
  Imported by Conversation (SAS builders on activity_events)
```

## The 3 tools

| Tool | Purpose |
|------|---------|
| `get_latest_context_items` | Current `context_version` + `context_items` |
| `get_feature_meta(feature_id)` | `meta_features` + `meta_events` (Instrumentation) |
| `publish_context_version` | New version: copy-forward + upserts/deletes |

```python
from context_agent import (
    get_context_catalog_tools,  # Agno Toolkit for another agent
    get_latest_context_items,   # direct call
    get_feature_meta,
    publish_context_version,
)

# Inside Conversation / other agent:
tools = [get_context_catalog_tools()]

# Or without Agno:
bundle = get_latest_context_items()
meta = get_feature_meta("01_express_checkout")
publish_context_version(
    context_version="v1",
    source="seed",
    summary="Bootstrap from base context",
    upserts=[
        {
            "kind": "entity",
            "item_key": "user",
            "label": "Traveller",
            "payload": {"primary_id_field": "user_id"},
        }
    ],
)
```

`get_postgres_sql_tools()` is optional admin/debug only.

## Postgres tables

See [`TABLES.md`](./TABLES.md). Context DDL is only `context_*`; meta DDL lives under Instrumentation.

## Environment

Repo-root `.env`:

```bash
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
```

`SESSION_DATABASE_URL` is only needed if some other agent uses Agno sessions against Postgres.

## Setup

```bash
uv sync
# Meta tables (Instrumentation):
uv run python -m instrumentation_agent.init_db
# Context tables (this package):
uv run python context_agent/scripts/init_schema.py
# Seed living context (entities, metrics, core funnel_steps):
uv run python context_agent/scripts/seed_v0.py

# Optional health check service (no agent):
PYTHONPATH=context_agent/src uv run uvicorn context_agent.app:app --reload --port 8001
```

Without `seed_v0`, `get_latest_context_items` returns empty and Conversation
`discover_schema` cannot invent schema (empty SchemaContext + notes).

## Related

- [`TABLES.md`](./TABLES.md)
- [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- [`../conversation_agent/README.md`](../conversation_agent/README.md)
