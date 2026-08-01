# Instrumentation Agent

Turns a feature **`spec.md` + `events.ndjson`** into production **ClickHouse** schemas (and load), and writes a **queryable metadata registry to Postgres** so Context / Conversation never re-scan raw NDJSON to learn what exists.

Parent overview: [`../README.md`](../README.md) (architecture + **`uv sync`** local setup).

> **Status:** design-only. Rebuild against this doc; shared env/app live at repo root.

## Role in the system

```
spec.md + events.ndjson (+ existing DDL envelope)
        │
        ▼
┌──────────────────────────────────────────────────┐
│  FastAPI app (hosts Agno AgentOS)                │
│  ┌────────────────────────────────────────────┐  │
│  │  Agno Instrumentation Agent (+ tools)      │  │
│  │  profile → plan DDL → apply CH → persist PG│  │
│  └────────────────────────────────────────────┘  │
│  + thin REST helpers (/health, registry read)    │
└───────────────┬───────────────┬──────────────────┘
                │               │
                ▼               ▼
        ClickHouse Cloud    Postgres (metadata)
        event fact tables   meta_* registry
                │               │
                └───────┬───────┘
                        ▼
              Context + Conversation agents
```

**Hosting model:** one **FastAPI** application **hosts** the Agno Instrumentation agent via **AgentOS** (`AgentOS(..., base_app=app)` → `get_app()`). Agno is not a separate process — agent run APIs and custom routes share the same FastAPI server.


| Store                | Owns                                                           |
| -------------------- | -------------------------------------------------------------- |
| **ClickHouse Cloud** | Feature/funnel **event tables**, optional MVs, NDJSON load     |
| **Postgres**         | **Metadata registry** (events, fields, schema decisions, runs) |


Do **not** store the metadata catalog in ClickHouse.

## Stack (this layer)


| Piece                  | Choice                                                                       |
| ---------------------- | ---------------------------------------------------------------------------- |
| Host app               | **FastAPI** — single process that **hosts** Agno                             |
| Agent runtime          | **Agno AgentOS** mounted on that FastAPI app (Instrumentation agent + tools) |
| Facts DB               | **ClickHouse Cloud**                                                         |
| Metadata DB            | **Postgres** (ClickHouse Cloud Postgres)                                     |
| CH DDL lint (optional) | **SQLGlot** (`dialect=clickhouse`) before apply — CREATE only, no DROP       |
| Tracing                | **Langfuse** (stamp `langfuse_trace_id` on decisions / runs)                 |


**SQLGlot note:** Conversation uses SQLGlot (and/or Agno `[SQLTools](https://docs.agno.com/use-cases/data-agents/querying-your-data)`) for analytics. Instrumentation only uses SQLGlot optionally to lint **DDL** before ClickHouse apply. Registry writes use SQLAlchemy/asyncpg.

**Downstream:** Conversation is an Agno **data agent** (introspect → SQL → insights) hosted on FastAPI — see `[../conversation_agent/README.md](../conversation_agent/README.md)`.

## Inputs / outputs


|         |                                                                                                                      |
| ------- | -------------------------------------------------------------------------------------------------------------------- |
| **In**  | `specs/<nn>_<name>/spec.md`, `events.ndjson`, existing envelope conventions from `data/ddl.sql`                      |
| **Out** | CH `CREATE TABLE` (+ optional MVs) + loaded rows; Postgres registry rows; Langfuse trace; plan JSON for judges/debug |


## Pipeline (deterministic core)

Prefer a **library pipeline** exposed as **Agno tools**, invoked when the hosted agent runs (and optionally from thin FastAPI helpers), so Day-2 schemas stay stable:

1. **Profile** — sample NDJSON; flatten nested JSON (`payment.latency_ms` → column); infer CH types; mark `in_spec` / `in_events`
2. **Plan** — one **table per event** (justify vs unified); envelope columns for joins; `ORDER BY` time + segment keys (**not** legacy `(id, …)`); `PARTITION BY toYYYYMM(timestamp)`
3. **Apply ClickHouse** — optional SQLGlot DDL lint → execute CREATE → load NDJSON
4. **Persist Postgres** — upsert registry + append decisions + `instrumentation_runs` row

The **Agno agent** (served by FastAPI/AgentOS) orchestrates those tools and records reasoning in Langfuse — it does not re-invent profiling inside the LLM.

## Postgres metadata schema (target)

```sql
CREATE TABLE instrumentation_runs (
  id UUID PRIMARY KEY,
  feature_id TEXT NOT NULL,
  strategy TEXT NOT NULL,
  strategy_rationale TEXT,
  context_version TEXT,
  langfuse_trace_id TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE meta_event_registry (
  id BIGSERIAL PRIMARY KEY,
  feature_id TEXT NOT NULL,
  event_name TEXT NOT NULL,
  target_table TEXT NOT NULL,
  funnel_stage INT NOT NULL DEFAULT 0,
  sample_count BIGINT NOT NULL DEFAULT 0,
  first_seen TIMESTAMPTZ,
  last_seen TIMESTAMPTZ,
  spec_path TEXT,
  notes TEXT,
  context_version TEXT,
  run_id UUID REFERENCES instrumentation_runs(id),
  registered_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (feature_id, event_name)
);

CREATE TABLE meta_field_registry (
  id BIGSERIAL PRIMARY KEY,
  feature_id TEXT NOT NULL,
  event_name TEXT NOT NULL,
  field_path TEXT NOT NULL,
  column_name TEXT NOT NULL,
  inferred_type TEXT NOT NULL,
  is_nullable BOOLEAN NOT NULL,
  null_rate REAL NOT NULL,
  example_values JSONB NOT NULL DEFAULT '[]',
  in_spec BOOLEAN NOT NULL DEFAULT false,
  in_events BOOLEAN NOT NULL DEFAULT true,
  registered_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (feature_id, event_name, field_path)
);

CREATE TABLE meta_schema_decisions (
  id BIGSERIAL PRIMARY KEY,
  feature_id TEXT NOT NULL,
  table_name TEXT NOT NULL,
  decision_kind TEXT NOT NULL,  -- order_by | partition | strategy | type | mv
  decision_value TEXT NOT NULL,
  rationale TEXT NOT NULL,
  langfuse_trace_id TEXT,
  registered_at TIMESTAMPTZ DEFAULT now()
);
```

Registry answers: event→table map, field paths/types/null rates, shared join keys, ORDER BY/partition rationale, PM questions supported.

## FastAPI hosts Agno (AgentOS)

```python
# conceptual wiring
from fastapi import FastAPI
from agno.agent import Agent
from agno.os import AgentOS

app = FastAPI(title="Instrumentation AgentHouse")
instrumentation_agent = Agent(name="Instrumentation", tools=[...])

agent_os = AgentOS(
    id="instrumentation",
    agents=[instrumentation_agent],
    base_app=app,   # FastAPI hosts Agno — same server, shared routes
)
app = agent_os.get_app()
```

- **Primary entry:** Agno/AgentOS run endpoints on the FastAPI app (agent executes tools).
- **Supporting REST** on the same app (non-LLM helpers):


| Method | Path                        | Behavior                                                               |
| ------ | --------------------------- | ---------------------------------------------------------------------- |
| `GET`  | `/v1/registry/{feature_id}` | Read events/fields/decisions from Postgres                             |
| `GET`  | `/health`                   | Postgres (and optional CH) connectivity                                |
| `POST` | `/v1/instrument`            | Optional convenience wrapper that triggers the same pipeline/agent run |


## Agno tools (wrap the library)


| Tool                        | Purpose                        |
| --------------------------- | ------------------------------ |
| `profile_feature`           | NDJSON + spec → profile / plan |
| `persist_metadata_registry` | Upsert Postgres `meta_`*       |
| `apply_clickhouse_schema`   | Lint (SQLGlot) + CREATE on CH  |
| `load_events`               | NDJSON → CH INSERT             |
| `list_registry`             | Read catalog for a feature     |


## Planned package layout (when implementing)

```
instrumentation_agent/
  README.md                 # this file
  src/instrumentation_agent/
    profiler.py             # NDJSON profile + type inference
    schema.py               # CH table plans / DDL strings
    models.py               # plan dataclasses
    pipeline.py             # run_instrumentation()
    db/                     # Postgres settings, SQLAlchemy, persist
    clickhouse/             # apply DDL, load, optional SQLGlot lint
    agents/                 # Agno Instrumentation agent + tools
    app/
      main.py               # FastAPI app + AgentOS(base_app=...) hosts the agent
      routes.py             # /health, /v1/registry helpers on same app
    cli.py                  # offline plan/apply helper
  sql/postgres_meta_registry.sql
  migrations/               # Alembic (or equivalent)
  .env.example              # no secrets committed
```

Config via env: `DATABASE_URL`, ClickHouse host/user/password, `SPECS_ROOT`, Langfuse keys. Never commit Postgres/CH credentials.

## Checklist

- Infer event types from `"event"`; one table per event vs unified — justify in Langfuse + `meta_schema_decisions`
- Flatten nested JSON; register each path in Postgres `meta_field_registry`
- Align envelope columns: `user_id`, `application_id`, `device_type`, `os`, `geoip_country_code`, `destination`, `timestamp`
- `ORDER BY` time + segment keys — **not** `(id, …)`
- `PARTITION BY` month on `timestamp`; TTL only if justified
- Prefer `LowCardinality` / concrete types over Nullable-String soup where safe
- Mark `in_spec` / `in_events`; never invent unseen columns
- Persist Postgres registry in the same run as CH apply (no orphan tables)
- Optional SQLGlot DDL lint before CH apply

## Specs this layer must generalize over


| #   | Feature                     | Core funnel                                           |
| --- | --------------------------- | ----------------------------------------------------- |
| 01  | Express Checkout            | shown → selected → saved_method → otp → confirmed     |
| 02  | Group / Family              | group_started → traveller_added/removed → submitted   |
| 03  | Status Sharing              | share → channel → link → opened → CTA                 |
| 04  | Abandoned Checkout Recovery | abandon → reminder → open/CTA → resumed → reconverted |
| 05  | Instant Forex               | offer → currency → amount → cart → purchased          |


Build for an unseen Day-2 sixth spec — do not hardcode only these five.

## Build order (this folder)

1. Postgres DDL/migrations + persist layer
2. Profiler + schema planner library + Agno tools
3. **FastAPI app that hosts Agno AgentOS** (`base_app`) + `/health` / registry routes
4. ClickHouse apply/load + optional SQLGlot DDL lint
5. Langfuse on each agent step

## Related

- Context updates: `[../context_agent/README.md](../context_agent/README.md)`
- Downstream **SQLTools data agent** + FastAPI: `[../conversation_agent/README.md](../conversation_agent/README.md)`
- Agno guide: [Querying your data](https://docs.agno.com/use-cases/data-agents/querying-your-data)
- Contest skill: `[.cursor/skills/clickathon-agenthouse/SKILL.md](../.cursor/skills/clickathon-agenthouse/SKILL.md)`

