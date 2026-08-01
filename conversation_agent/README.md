# Conversation Agent

PM-facing **data agent** in the [Agno “Querying your data”](https://docs.agno.com/use-cases/data-agents/querying-your-data) style: **SQLTools** for schema introspection + SQL, grounded in our Postgres registry / context, with analytics executed against **ClickHouse**. Exposed by a **FastAPI** server that **hosts Agno AgentOS**.

Parent overview: [`../README.md`](../README.md) (architecture + **`uv sync`** local setup).

> **Status:** design-only. Rebuild against this doc; shared env/app live at repo root.

## Role in the system

```
Postgres (meta_* + context)     ClickHouse (event facts)
        │                                │
        │  SQLTools (introspect/query)   │  SQLTools or CH tool
        │  read-only engine              │  (+ SQLGlot validate)
        ▼                                ▼
┌──────────────────────────────────────────────────┐
│  FastAPI app (hosts Agno AgentOS)                │
│  ┌────────────────────────────────────────────┐  │
│  │  Agno Conversation Agent                   │  │
│  │  list_tables → describe_table → run SQL    │  │
│  │  → PM insight (why, segment, recommendation)│ │
│  └────────────────────────────────────────────┘  │
│  Agent session db: PostgresDb (separate from     │
│  warehouse SQLTools engines — per Agno docs)     │
└──────────────────────────────────────────────────┘
```

This is the contest **Analytics** layer as a conversational data agent.

## Agno pattern (canonical)

Follow [Querying your data](https://docs.agno.com/use-cases/data-agents/querying-your-data):

| Piece | Our wiring |
|-------|------------|
| `Agent` + `SQLTools` | Conversation agent tools |
| `SQLTools(db_engine=...)` | **Read-only** SQLAlchemy engines (see below) |
| `list_tables` / `describe_table` | Introspect **before** writing SQL — never guess columns |
| `run_sql_query` | Execute; use `limit=None` when aggregates need all groups |
| `db=PostgresDb(...)` | **Agent sessions / memory only** — not the warehouse |
| Hard boundary | Non-owner DB roles; read-only session where applicable ([safe data access](https://docs.agno.com/use-cases/data-agents/safe-data-access)) |

**Important (from Agno):** agent `db` and `SQLTools` connections stay **distinct**. Sessions ≠ analytics warehouse.

### Conceptual agent

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.tools.sql import SQLTools
from sqlalchemy import create_engine

# Agent sessions / traces state (not the analytics catalog)
agent_db = PostgresDb(db_url=SESSION_DATABASE_URL)

# Metadata registry — read-only Postgres (meta_event_registry, …)
registry_engine = create_engine(
    REGISTRY_DATABASE_URL,
    connect_args={"options": "-c default_transaction_read_only=on"},
)

# Event facts — ClickHouse via SQLAlchemy (or a dedicated CH query tool)
facts_engine = create_engine(CLICKHOUSE_SQLALCHEMY_URL)

conversation_agent = Agent(
    name="Conversation",
    db=agent_db,
    tools=[
        SQLTools(db_engine=registry_engine),  # introspect + query meta_*
        SQLTools(db_engine=facts_engine),     # or custom tool: SQLGlot → CH
    ],
    instructions=(
        "Introspect schema (list_tables / describe_table) before writing SQL. "
        "Prefer meta_* registry for field discovery; run aggregates on fact tables. "
        "Answer with numbers and the exact query. Never guess column names. "
        "Cut by device_type, geoip_country_code, destination. "
        "Use limit=None on run_sql_query when GROUP BY needs every row."
    ),
)
```

### ClickHouse + SQLGlot

Agno `SQLTools` is SQLAlchemy-oriented. For ClickHouse:

1. Prefer a **ClickHouse SQLAlchemy** engine behind `SQLTools` when workable, **or**
2. Custom tool: draft SQL → **SQLGlot** parse/validate (`dialect=clickhouse`, SELECT-only) → `clickhouse-connect` execute → return aggregates

Either way: introspect first (registry and/or `describe_table`), then query; LLM sees aggregates only.

## FastAPI hosts the agent

Same hosting model as Instrumentation: **FastAPI + AgentOS** exposes the Conversation agent (no sidecar).

```python
from fastapi import FastAPI
from agno.os import AgentOS

app = FastAPI(title="AgentHouse Conversation")
agent_os = AgentOS(
    id="conversation",
    agents=[conversation_agent],
    base_app=app,
)
app = agent_os.get_app()
# uvicorn: AgentOS run APIs + optional /health on the same app
```

Clients talk to the **hosted Agno agent** over the FastAPI server (AgentOS routes). Optional thin helpers: `/health`, `/v1/context/latest` (read-only).

## Inputs / outputs

| | |
|--|--|
| **In** | PM / user question; Postgres `meta_*` + context snapshots; ClickHouse fact tables |
| **Out** | Insight summary (why + segment + recommendation), exact SQL used, confidence/caveats, Langfuse/Agno trace |

## Rules

- [ ] Introspect (`list_tables` / `describe_table` or registry SQL) **before** generating SQL
- [ ] Never guess column names — match Instrumentation registry / live schema
- [ ] Push computation into ClickHouse (`uniq`, `windowFunnel`, `sequenceMatch`, group-bys); interpret **aggregates only**
- [ ] Always cut by `device_type`, `geoip_country_code`, and `destination` before concluding
- [ ] Link findings to known issues in context (K1–K7) when relevant
- [ ] Answer PM questions from each `spec.md`
- [ ] Include confidence / caveats; cite `context_version`
- [ ] Pass `limit=None` when a full `GROUP BY` is required ([Agno note](https://docs.agno.com/use-cases/data-agents/querying-your-data))

## Insight shape (target output)

1. **What** — metric / funnel step (numbers from SQL)  
2. **Where** — device × geo × destination  
3. **Why** — linked to context (K-issue, coupon, seasonality)  
4. **Do** — PM recommendation  
5. **Confidence** — sample size, data quality, metric conflicts  
6. **SQL** — exact query run (per Agno data-agent style)

## Specs to support

| # | Feature | Example analytic focus |
|---|---------|------------------------|
| 01 | Express Checkout | OTP success, latency, vs standard pay path |
| 02 | Group / Family | group size, traveller add/remove drop, submit rate |
| 03 | Status Sharing | channel mix, recipient new-user CTA |
| 04 | Abandoned Checkout Recovery | drop_step, reminder → reconvert lift |
| 05 | Instant Forex | offer → purchase, FX pair / addon value |

Day-2 sixth spec uses the **same** agent + FastAPI path.

## Planned layout

```
conversation_agent/
  README.md
  src/conversation_agent/
    agents/conversation.py   # Agent + SQLTools + instructions
    tools/clickhouse_sql.py  # optional SQLGlot → CH execute
    app/main.py              # FastAPI + AgentOS(base_app=...) hosts agent
    app/routes.py            # /health helpers
  .env.example
```

## Related

- Agno guide: [Querying your data](https://docs.agno.com/use-cases/data-agents/querying-your-data)
- Registry writer: [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- Living context: [`../context_agent/README.md`](../context_agent/README.md)
- Contest query hints: [`.cursor/skills/clickathon-agenthouse/reference.md`](../.cursor/skills/clickathon-agenthouse/reference.md)
