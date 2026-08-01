# Conversation Agent (Visualization)

NL analytics workflow: **question → schema → viz plan → SQL+execute**.  
Primary path: **template builders + clickhouse-connect**.  
Fallback: **LLM `generate_query` + ClickHouse MCP** (previous behaviour).

Parent overview: [`../README.md`](../README.md).

## Pipeline

```
User question
      │
      ▼
┌─────────────────┐
│ discover_schema │  context catalog tools + SAS shape
│                 │  (activity_events envelope + event_info)
│                 │  → SchemaContext   (LLM)
└────────┬────────┘
         ▼
┌─────────────────┐
│ plan_visualization │  SchemaContext → VizSpec          (LLM)
└────────┬────────┘
         ▼
┌─────────────────────────────────────────────────────┐
│ run_analytics                                        │
│  1) VizSpec → AnalyticsPlan → SQL template           │
│  2) SQLGlot validate → clickhouse-connect execute    │
│  else → LLM QuerySpec + MCP run_query (fallback)     │
└─────────────────────────────────────────────────────┘
```

## Deterministic builders (`query_builders.py`)

| `kind` | SQL pattern |
|--------|-------------|
| `funnel` | `windowFunnel` on `atlys.activity_events` (`event_name`) |
| `timeseries` | daily `count` / `uniqExact` by `event_name` |
| `breakdown` / `top_n` | `GROUP BY` envelope segment |
| `metric` | counts or rate (`event_names` = numerator,denominator) |
| `comparison` | current vs previous half-window |

Unsupported / invalid plans fall back to LLM + MCP.

## Layout

```
conversation_agent/
├── analytics.py              # run_analytics() orchestration
├── clickhouse_client.py      # SQLGlot + clickhouse-connect
├── query_builders.py         # AnalyticsPlan + SQL templates
├── tools.py                  # Agno Toolkit (run_analytics)
├── visualization_agent.py    # workflow + CLI / AgentOS
├── steps/
│   ├── discover_schema.py
│   ├── plan_visualization.py
│   ├── run_analytics.py      # workflow step
│   ├── generate_query.py     # fallback LLM
│   └── execute.py            # legacy MCP-only step
└── …
```

## Setup / run

Use the **project venv** (`uv`), not system `pip` (Apple CLT Python can't install `mcp`).

```bash
uv sync
# Build SAS fact table from existing per-event CH tables (once):
uv run python conversation_agent/scripts/build_activity_events.py --drop
uv run python -m conversation_agent.visualization_agent "conversion by device last 30 days"
uv run python -m conversation_agent.visualization_agent --os
```

`--sample N` loads at most N rows per source table for a quick smoke test.
## Tool usage (other agents)

```python
from conversation_agent.tools import get_analytics_tools

tools = [get_analytics_tools()]
# tool: run_analytics(kind="funnel", event_names="a,b,c", dimensions="device_type")
```

## Related

- Instrumentation: [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- Context: [`../context_agent/README.md`](../context_agent/README.md)
