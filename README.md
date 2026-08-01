# Click-a-thon 2026 · Atlys AgentHouse

Agentic analytics on **ClickHouse Cloud**: a feature `spec.md` + raw `events.ndjson` become production schemas, a **queryable metadata registry**, PM-ready insights, and a living business context layer — all **Langfuse-traced**.

## High-level design (HLD)

```
specs/<nn>_*/spec.md + events.ndjson
base_context.md / existing DDL
              │
              ▼
┌─────────────────────────────────┐
│     Instrumentation Agent       │
│  infer events → DDL → load      │
│  + queryable metadata registry   │
└───────────────┬─────────────────┘
                │ schema + registry
                ▼
          ClickHouse Cloud
                │
        ┌───────┴────────┐
        ▼                ▼
┌───────────────┐  ┌───────────────┐
│ Conversation  │◄─│ Context Agent │
│ Agent         │  │ (living layer)│
│ (analytics /  │  │               │
│  PM insights) │  └───────┬───────┘
└───────┬───────┘          │
        │                  │
        ▼                  ▼
  PM insight summary   updated context
        │
        └── all agent steps → Langfuse
```

**Flow:** Instrumentation turns a feature spec into ClickHouse tables and registers what the events actually contain. Context keeps business definitions fresh from those schema/registry changes. Conversation (analytics) queries facts + registry + latest context and returns PM-actionable insights.

## Agents at a glance

| Layer | Folder | Responsibility |
|-------|--------|----------------|
| **Instrumentation** | [`instrumentation_agent/`](./instrumentation_agent/) | `spec.md` + NDJSON → DDL, load, **queryable metadata registry** |
| **Context** | [`context_agent/`](./context_agent/) | Living context; refresh on schema/registry change; flag contradictions |
| **Conversation** | [`conversation_agent/`](./conversation_agent/) | Analytics over CH + context → PM insights (why, segment, recommendation) |

Layer design, checklists, and schemas live in each folder’s `README.md`.

## Stack overview

| Item | Choice |
|------|--------|
| Primary DB | ClickHouse Cloud |
| Metadata | Queryable `meta_*` tables (owned by Instrumentation) |
| Existing data | 8 funnel/supporting event tables (Parquet + DDL) |
| New features | `specs/01`–`05` — brief + NDJSON only (no pre-made schemas) |
| Day 2 | Unseen 6th spec — same pipeline + Langfuse proof |
| Tracing | Langfuse on every agent step |

**Out of scope:** auth, prod deploy, streaming ingest, polished frontends.

## Repo map

```
instrumentation_agent/   # schema + registry layer
context_agent/           # living business context
conversation_agent/      # analytics / PM conversation layer
specs/                   # feature briefs + events.ndjson (when present)
data/                    # existing DDL, Parquet, load scripts (when present)
.cursor/skills/…         # contest skill + reference
```

## Evaluation focus

- Schema quality (keys, partition, types, MVs)
- Registry quality (event/field coverage backed by NDJSON)
- Insight quality (actionable *why*)
- Context freshness after new tables
- Full Langfuse reasoning chain (incl. Day-2 sixth spec)

## Suggested build order

1. ClickHouse Cloud + Langfuse; load existing tables  
2. [`instrumentation_agent`](./instrumentation_agent/) — NDJSON → DDL → load → `meta_*`  
3. [`context_agent`](./context_agent/) — react to registry/schema changes  
4. [`conversation_agent`](./conversation_agent/) — registry + context + facts → insights  
5. Run specs 01–05 end-to-end; harden for unseen Day-2

## Canonical references

| Resource | Purpose |
|----------|---------|
| [`.cursor/skills/clickathon-agenthouse/SKILL.md`](./.cursor/skills/clickathon-agenthouse/SKILL.md) | Agent workflow |
| [`.cursor/skills/clickathon-agenthouse/reference.md`](./.cursor/skills/clickathon-agenthouse/reference.md) | Spec hints, K1–K7, query patterns |
| [`.cursor/rules/clickathon-stack.mdc`](./.cursor/rules/clickathon-stack.mdc) | Stack constraints |
| `problem_statement.md` / `base_context.md` | Challenge + imperfect business context (when in package) |
