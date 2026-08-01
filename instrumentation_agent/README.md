# Instrumentation Agent

Turns a feature **`spec.md` + `events.ndjson`** into production ClickHouse schemas, loads the data, and builds a **queryable metadata registry** so Analytics/Context never re-scan raw NDJSON to learn what exists.

Parent overview: [`../README.md`](../README.md)

## Role in the system

```
spec.md + events.ndjson (+ existing DDL envelope)
        │
        ▼
  Instrumentation Agent
        │
        ├── CREATE TABLE / MVs  →  ClickHouse Cloud
        ├── INSERT / load NDJSON
        └── meta_* registry writes
                │
                ├──► Context Agent (schema changelog)
                └──► Conversation Agent (discover dimensions)
```

## Inputs / outputs

| | |
|--|--|
| **In** | `specs/<nn>_<name>/spec.md`, sample of `events.ndjson`, existing `data/ddl.sql` for join keys |
| **Out** | Production DDL (+ optional MVs), loaded fact tables, **`meta_*` registry rows**, Langfuse trace |

## Metadata registry (queryable catalog)

Durable “catalog of truth” derived from **events + spec** — do not invent columns the events never carry.

Answers:

- Which event types exist, and which tables they map to?
- Which fields appear (path, inferred CH type, null rate)?
- Which envelope keys are shared for joins?
- What `ORDER BY` / `PARTITION BY` / TTL choices were made and why?
- Which PM questions in `spec.md` this instrumentation supports?

### Proposed ClickHouse tables

```sql
CREATE TABLE IF NOT EXISTS meta_event_registry
(
    feature_id       LowCardinality(String),
    event_name       LowCardinality(String),
    target_table     LowCardinality(String),
    funnel_stage     UInt16,
    sample_count     UInt64,
    first_seen       DateTime64(3),
    last_seen        DateTime64(3),
    spec_path        String,
    notes            String,
    registered_at    DateTime64(3) DEFAULT now64(3),
    context_version  String
)
ENGINE = ReplacingMergeTree(registered_at)
ORDER BY (feature_id, event_name);

CREATE TABLE IF NOT EXISTS meta_field_registry
(
    feature_id       LowCardinality(String),
    event_name       LowCardinality(String),
    field_path       String,
    column_name      String,
    inferred_type    LowCardinality(String),
    is_nullable      UInt8,
    null_rate        Float32,
    example_values   Array(String),
    in_spec          UInt8,
    in_events        UInt8,
    registered_at    DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(registered_at)
ORDER BY (feature_id, event_name, field_path);

CREATE TABLE IF NOT EXISTS meta_schema_decisions
(
    feature_id        LowCardinality(String),
    table_name        LowCardinality(String),
    decision_kind     LowCardinality(String),
    decision_value    String,
    rationale         String,
    registered_at     DateTime64(3) DEFAULT now64(3),
    langfuse_trace_id String
)
ENGINE = MergeTree
ORDER BY (feature_id, table_name, registered_at);
```

### Example registry queries

```sql
SELECT event_name, target_table, funnel_stage, sample_count
FROM meta_event_registry FINAL
WHERE feature_id = '01_express_checkout'
ORDER BY funnel_stage;

SELECT field_path, column_name, inferred_type, null_rate
FROM meta_field_registry FINAL
WHERE feature_id = '01_express_checkout'
  AND in_events = 1
  AND null_rate < 0.5
ORDER BY event_name, field_path;

SELECT column_name, groupArray(DISTINCT feature_id) AS features
FROM meta_field_registry FINAL
WHERE field_path IN ('user_id', 'application_id', 'destination', 'device_type')
GROUP BY column_name;
```

## Checklist

- [ ] Infer event types from `"event"`; one table per event vs typed unified — justify in Langfuse + `meta_schema_decisions`
- [ ] Flatten nested JSON into typed columns; register each path in `meta_field_registry`
- [ ] Align envelope columns for joins: `user_id`, `application_id`, `device_type`, `os`, `geoip_country_code`, `destination`, `timestamp`
- [ ] `ORDER BY` for time + segment keys — **not** legacy `(id, …)`
- [ ] `PARTITION BY` (typically month on `timestamp`); TTL only if justified
- [ ] Prefer `LowCardinality` / concrete types over Nullable-String soup where safe
- [ ] Mark `in_spec` / `in_events`; never invent unseen columns
- [ ] Write registry in the same run as DDL + load (no orphan tables)

## Specs this layer must generalize over

| # | Feature | Core funnel |
|---|---------|-------------|
| 01 | Express Checkout | shown → selected → saved_method → otp → confirmed |
| 02 | Group / Family | group_started → traveller_added/removed → submitted |
| 03 | Status Sharing | share → channel → link → opened → CTA |
| 04 | Abandoned Checkout Recovery | abandon → reminder → open/CTA → resumed → reconverted |
| 05 | Instant Forex | offer → currency → amount → cart → purchased |

Build the pipeline for an unseen Day-2 sixth spec — do not hardcode only these five.

## Hard constraints

- ClickHouse is the primary datastore; schemas must be columnar-optimized
- Prefer evidence from NDJSON samples over memorized field lists
- Every decision traced in Langfuse

## Related

- Context updates: [`../context_agent/README.md`](../context_agent/README.md)
- Downstream insights: [`../conversation_agent/README.md`](../conversation_agent/README.md)
- Field hints / quirks: [`.cursor/skills/clickathon-agenthouse/reference.md`](../.cursor/skills/clickathon-agenthouse/reference.md)
