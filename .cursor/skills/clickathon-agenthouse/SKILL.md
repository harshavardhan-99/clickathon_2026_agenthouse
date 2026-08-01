---
name: clickathon-agenthouse
description: >-
  Orient and build the Click-a-thon 2026 Atlys AgentHouse system: Instrumentation,
  Analytics, and Context agents on ClickHouse with Langfuse tracing. Use when
  working in this repo, designing schemas from feature specs, writing analytics
  insights, maintaining base_context, loading data/, or preparing the unseen Day-2
  sixth spec pipeline.
---

# Click-a-thon AgentHouse

Build three cooperating agents + tracing so a feature spec becomes production-ready
ClickHouse schemas and PM-ready insights, with a living context layer.

## First actions (every new session)

1. Skim `problem_statement.md` (judging + constraints).
2. Confirm data is real Parquet (not LFS pointers): `wc -c data/*.parquet` — each should be MBs, not ~133B. If pointers: `git lfs pull`.
3. Read `base_context.md` **critically** — contradictions vs `data/ddl.sql` are expected.
4. Treat `specs/*/spec.md` + `events.ndjson` as Instrumentation inputs (no pre-made schemas).

## System shape

```
Feature spec + NDJSON
        │
        ▼
┌───────────────────┐     updates      ┌─────────────────┐
│ Instrumentation   │ ───────────────► │ Context Agent   │
│ Agent             │                  │ (living layer)  │
└─────────┬─────────┘                  └────────┬────────┘
          │ CREATE / load                       │ latest defs
          ▼                                     ▼
     ClickHouse  ◄──────────────────── Analytics Agent
          │                                     │
          └──────── aggregates ────────────────┘
                                                ▼
                                         PM insight summary
                     All steps → Langfuse traces
```

## Agent responsibilities

### 1. Instrumentation Agent

**Input:** `specs/<nn>_<name>/spec.md` + sample of `events.ndjson`  
**Output:** production-ready `CREATE TABLE` (+ optional MVs), then execute against team ClickHouse.

Checklist:

- [ ] Infer event types from `"event"` field; design **one table per event** or a typed unified table — justify the choice in the trace
- [ ] Flatten nested JSON (e.g. Express `payment.latency_ms`) into typed columns
- [ ] Shared envelope columns aligned with existing tables where joins matter (`user_id`, `application_id`, `device_type`, `os`, `geoip_country_code`, `destination`, `timestamp`)
- [ ] `ORDER BY` for real query patterns (time + segment keys), **not** `(id, …)`
- [ ] `PARTITION BY` (typically month on `timestamp`); consider TTL if justified
- [ ] Prefer `LowCardinality` / concrete types over wide Nullable-String soup where safe
- [ ] Map load path: NDJSON → ClickHouse (INSERT / file insert)

Do **not** invent columns the events never carry. Prefer evidence from NDJSON samples.

### 2. Analytics Agent

**Input:** instrumented + existing tables + **current** context layer  
**Output:** insight summaries a PM would act on (why + segment + recommendation).

Rules:

- Push computation into ClickHouse (`uniq`, `windowFunnel`, `sequenceMatch`, group-bys). LLM interprets aggregates only.
- Always cut by device, geo, and destination before concluding.
- Link findings to known issues in context (K1–K7) when relevant.
- Answer the PM questions listed in each `spec.md`.
- Include confidence / caveats (sample size, seasonality, coupon campaigns).

### 3. Context Agent

**Input:** `base_context.md` + DDL / new tables  
**Output:** updated context (storage is your design: file, CH table, vector store — justify).

Must:

- Auto-update when Instrumentation adds tables/columns
- Feed Analytics the **latest** context (no stale snapshot)
- Surface contradictions (e.g. conversion denominator: sessions vs `application_started`; `eta_shown` in DDL vs `visa_issuance_eta_days` in prose)
- Keep entity join map current

### 4. Tracing + visualization

- Langfuse: every agent step — inputs, tools/SQL, context version used, outputs
- Viz (dashboard / light UI / structured CLI): schema changelog, insights + confidence, context diffs
- Day-2 sixth-spec submission needs matching traces or it scores nothing

## Data model cheat sheet

Funnel joins: `user_id` whole journey; `application_id` from `application_started` onward. Order by `timestamp`.

| Table | Kind | Key columns |
|-------|------|-------------|
| destination_card_clicked | funnel | destination, visa_type, card_type, flow |
| application_started | funnel | purpose, eta_shown, co_travelers |
| document_uploaded | funnel | doc_type, capture_mode, retry_count, is_crossed_failed_attempt_threshold |
| purchase_completed | funnel / conversion | value, currency, coupon_*, insurance_* |
| search_typed | supporting | search_term, results_count |
| landing_page_scrolled | supporting | scroll_depth_pct, time_on_page_s |
| auth_completed | supporting | auth_method, is_new_user |
| pay_now_clicked | supporting | payment_method, amount (click ≠ pay) |

Load: `cd data && CH='clickhouse-client --host … --user … --password … --secure' DB=atlys ./load.sh`

## Five known specs (build the pipeline, don't hardcode)

| # | Feature | Core funnel in events |
|---|---------|------------------------|
| 01 | Express Checkout | shown → selected → saved_method → otp → confirmed |
| 02 | Group / Family | group_started → traveller_added/removed → submitted |
| 03 | Status Sharing | share → channel → link → opened → CTA |
| 04 | Abandoned Checkout Recovery | abandon → reminder → open/CTA → resumed → reconverted |
| 05 | Instant Forex | offer → currency → amount → cart → purchased |

## Evaluation (optimize for these)

- Schema quality (keys, partition, types, useful MVs)
- Insight quality (actionable *why*)
- Context freshness after new tables
- Full Langfuse reasoning chain
- Unseen 6th-spec output + proof trace

## Additional resources

- Spec & event field details: [reference.md](reference.md)
- Canonical challenge text: `problem_statement.md`, `base_context.md`
