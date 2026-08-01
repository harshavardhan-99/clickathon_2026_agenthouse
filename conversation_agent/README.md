# Conversation Agent (Visualization)

NL analytics workflow: **question → schema → viz plan → ClickHouse SQL → execute**. Contest **Analytics** layer, Langfuse-traced, exposed as CLI or Agno AgentOS.

Parent overview: [`../README.md`](../README.md).

## Pipeline

```
User question
      │
      ▼
┌─────────────────┐
│ discover_schema │  schema_context.md → SchemaContext
└────────┬────────┘
         ▼
┌─────────────────┐
│ plan_visualization │  SchemaContext → VizSpec
└────────┬────────┘
         ▼
┌─────────────────┐
│ generate_query  │  VizSpec + funnel skill → QuerySpec (one SELECT)
└────────┬────────┘
         ▼
┌─────────────────┐
│ execute         │  ClickHouse MCP run_query → ExecuteResult
└─────────────────┘
```

LLM steps interpret schema / plan / SQL. Execution is deterministic via MCP — aggregates only, no raw event dumps into the model.

## Layout

```
conversation_agent/
├── README.md
├── config.py                 # loads repo-root .env
├── models.py                 # SchemaContext, VizSpec, QuerySpec, ExecuteResult
├── shared.py                 # model builder, Langfuse, MCP helpers
├── visualization_agent.py    # workflow assembly + CLI / AgentOS entry
├── visualization_agent_old.py # legacy single-agent MCP path (AgentOS optional)
├── context/
│   └── schema_context.md     # ground-truth tables / columns / events
├── skills/
│   └── generate_query.md     # ClickHouse funnel / windowFunnel skill
└── steps/
    ├── discover_schema.py
    ├── plan_visualization.py
    ├── generate_query.py
    ├── execute.py
    └── glue.py               # packs question + schema for viz planner
```

## Setup

From repo root (Python 3.12+):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
pip install -U "agno[os]"   # needed for AgentOS serve mode
cp .env.example .env        # fill ClickHouse, model key, optional Langfuse
```

Required for a working run:

| Var | Purpose |
|-----|---------|
| `CLICKHOUSE_*` | Cloud connection (MCP inherits these) |
| `MODEL_PROVIDER` / `MODEL_ID` | `claude` \| `gemini` \| `openai` |
| Matching API key | e.g. `ANTHROPIC_API_KEY` |

Optional: `LANGFUSE_*`, `AGENTOS_*` (serve mode).

## Run

```bash
# CLI — default demo prompt
python -m conversation_agent.visualization_agent

# CLI — custom question
python -m conversation_agent.visualization_agent "OTP success by device last 30 days"

# AgentOS (FastAPI) — connect from https://os.agno.com
python -m conversation_agent.visualization_agent --os
python -m conversation_agent.visualization_agent --os --port 7777
```

CLI prints `ExecuteResult` JSON (`sql`, `columns`, `rows`, `row_count`, optional `error`).

AgentOS surfaces:

- Workflow `visualization-agent` — the four-step pipeline above
- Legacy agent `visualization-agent-legacy` — single MCP agent (old path)

## Contracts (`models.py`)

| Step | Output |
|------|--------|
| `discover_schema` | `SchemaContext` — tables, columns, events |
| `plan_visualization` | `VizSpec` — kind, metrics, dimensions, window |
| `generate_query` | `QuerySpec` — one aggregate `SELECT` (+ funnel metadata) |
| `execute` | `ExecuteResult` — columns + rows from MCP |

`AnalyticsResponse` / insight blocks exist for a future frontend; the workflow’s final output this iteration is `ExecuteResult`.

## Rules

- Schema comes from `context/schema_context.md` — do not invent tables/columns.
- Prefer `atlys.funnel_events` for funnel SQL (`event` + `timestamp`); see `skills/generate_query.md`.
- Push work into ClickHouse (`uniq`, `windowFunnel`, group-bys); interpret aggregates only.
- Cut by `device_type`, `geoip_country_code`, `destination` when the question implies segments.

## Related

- Instrumentation: [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- Context: [`../context_agent/README.md`](../context_agent/README.md)
- Agno workflows: [docs.agno.com](https://docs.agno.com)
