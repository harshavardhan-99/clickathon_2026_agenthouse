# Click-a-thon 2026 · Atlys AgentHouse

Agentic analytics for Atlys: **feature spec + NDJSON → ClickHouse schemas + Postgres metadata → PM insights**, with three Agno agents **hosted on one FastAPI app** (AgentOS). Conversation follows Agno’s [SQLTools data-agent](https://docs.agno.com/use-cases/data-agents/querying-your-data) style. Traced with **Langfuse**.

---

## 1. Architecture

```
specs/*/spec.md + events.ndjson
base_context.md
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI  ── hosts ──►  Agno AgentOS                │
│    Instrumentation │ Context │ Conversation         │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
           ▼                          ▼
   ClickHouse Cloud              Postgres
   event fact tables             meta_* registry
                                 context snapshots
                                 Agno session db*
           │                          │
           └────────────┬─────────────┘
                        ▼
              PM insights + Langfuse traces

* Session PostgresDb ≠ SQLTools warehouse engines ([Agno](https://docs.agno.com/use-cases/data-agents/querying-your-data))
```

| Layer | Docs | Runtime code |
|-------|------|----------------|
| **Instrumentation** | [`instrumentation_agent/`](./instrumentation_agent/) | `instrumentation_agent/{routes,tools,interfaces,models,utils}` |
| **Context** | [`context_agent/`](./context_agent/) | (same pattern under `context_agent/`) |
| **Conversation** | [`conversation_agent/`](./conversation_agent/) | (same pattern under `conversation_agent/`) |

| Store | Owns |
|-------|------|
| **ClickHouse** | Event / funnel fact tables |
| **Postgres** | Metadata registry, context snapshots, agent sessions |

**Runtime:** FastAPI hosts Agno (`AgentOS(base_app=app)`). No sidecar.  
**Analytics SQL:** SQLTools + **SQLGlot** (`clickhouse`) on the Conversation path.  
**Out of scope:** auth, prod deploy, streaming ingest, polished UIs.

Layer detail lives only in each folder’s `README.md` — keep this file as the map.

---

## 2. Repository structure

```
clickathon_2026_agenthouse/
├── README.md
├── pyproject.toml / uv.lock / .python-version
├── .env.example
├── app/
│   └── main.py                    ← thin FastAPI host (mounts agent routers)
├── instrumentation_agent/         ← full layer package
│   ├── routes/                    ← thin FastAPI routers
│   ├── interfaces/                ← entrypoints used by routers/tools
│   ├── models/                    ← request/response + domain models
│   ├── db/                        ← CRUD classes (meta_features, meta_events)
│   ├── utils/                     ← shared helpers; ClickHouse via SQLGlot
│   ├── tools/                     ← Agno Toolkits
│   ├── sql/
│   ├── settings.py
│   └── init_db.py
├── context_agent/                 ← layer design (+ code later)
├── conversation_agent/            ← layer design (+ code later)
├── tests/
└── .cursor/skills|rules/
```

---

## 3. Local development (uv)

### Prerequisites

- [uv](https://docs.astral.sh/uv/) installed  
- Python **3.12+** (uv will fetch it if needed)

```bash
# install uv if missing (Linux/macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Create / sync the environment

From the **repo root**:

```bash
cd clickathon_2026_agenthouse

# Install deps from pyproject.toml into .venv (create if needed)
uv sync

# Optional: include dev tools (pytest, ruff)
uv sync --group dev
```

Activate (optional — `uv run` works without activating):

```bash
source .venv/bin/activate    # Linux/macOS
```

### Configure secrets

```bash
cp .env.example .env
# edit .env — Postgres, ClickHouse, model keys, Langfuse
```

Never commit `.env`.

### Common commands

```bash
# run any tool in the project env
uv run python -V
uv run pytest

# after code exists — start the FastAPI + Agno host
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# bootstrap Postgres meta tables
uv run python -m instrumentation_agent.init_db

# add a dependency later
uv add <package>
uv add --group dev <package>
```

Re-run **`uv sync`** after pulling when `pyproject.toml` / `uv.lock` change.

---

## 4. Stack

| Piece | Choice |
|-------|--------|
| Package / env | **uv** (`uv sync`) |
| Runtime | **FastAPI** hosts **Agno AgentOS** |
| Query agent | Agno **`SQLTools`** ([docs](https://docs.agno.com/use-cases/data-agents/querying-your-data)) |
| Event store | **ClickHouse Cloud** |
| Metadata / sessions | **Postgres** |
| SQL safety | **SQLGlot** (`clickhouse`) |
| Tracing | **Langfuse** |

---

## 5. Build order

1. Postgres `meta_*` + Instrumentation write path (`instrumentation_agent/`)  
2. Thin `app/main.py` FastAPI host + AgentOS for Instrumentation  
3. Context agent package (same layout)  
4. Conversation SQLTools data agent  
5. Specs 01–05 E2E → Day-2 unseen sixth spec  

---

## 6. Evaluation

Schema quality · registry quality · actionable insights · context freshness · full Langfuse/Agno traces (Day-2 proof required).

---

## 7. References

| Doc | Purpose |
|-----|---------|
| [Agno: Querying your data](https://docs.agno.com/use-cases/data-agents/querying-your-data) | SQLTools data-agent pattern |
| [`instrumentation_agent/README.md`](./instrumentation_agent/README.md) | Instrumentation design |
| [`context_agent/README.md`](./context_agent/README.md) | Context design |
| [`conversation_agent/README.md`](./conversation_agent/README.md) | Conversation / SQLTools design |
| [`.cursor/skills/clickathon-agenthouse/SKILL.md`](./.cursor/skills/clickathon-agenthouse/SKILL.md) | Contest workflow |
| [`.cursor/rules/clickathon-stack.mdc`](./.cursor/rules/clickathon-stack.mdc) | Stack constraints |
