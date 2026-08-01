# Context Agent — Postgres tables (simple)

**Goal:** few tables, clear ownership, fast reads — **no JSON columns**.

| Store | Owns |
|-------|------|
| **ClickHouse** | Event data, aggregates, MVs |
| **Postgres** | What exists (meta) + what it means (context) |

| Writer | Tables |
|--------|--------|
| Instrumentation | `instrumentation_runs`, `meta_objects`, `meta_events`, `meta_fields` |
| Context | `context_versions` + relational context tables |
| Conversation | read-only |

**Common columns on every table:** `created_at`, `updated_at` (`TIMESTAMPTZ`).  
No `langfuse_trace_id`. No JSON / JSONB.

```
instrumentation_runs
meta_objects
meta_events
 └── meta_fields

context_versions          ← is_current pointer
 ├── context_entities
 ├── context_metrics
 ├── context_joins
 ├── context_funnels
 │    └── context_funnel_steps
 ├── context_known_issues
 └── context_contradictions
```

---

## Meta (Instrumentation)

### 1. `instrumentation_runs`

**Use:** Audit each Instrumentation run.

| id | feature_id | strategy | notes | created_at | updated_at |
|----|------------|----------|-------|------------|------------|
| `a1b2…` | `01_express_checkout` | `one_table_per_event` | Initial instrument | `2026-06-08 12:00:00+00` | `2026-06-08 12:01:00+00` |
| `d4e5…` | `01_express_checkout` | `one_table_per_event` | Added field `otp_channel` | `2026-06-10 09:00:00+00` | `2026-06-10 09:01:00+00` |

---

### 2. `meta_objects`

**Use:** All ClickHouse objects in one catalog (`raw` / `aggregate` / `mv` / `view`).

| name | feature_id | kind | engine | order_by | partition_by | source | target | grain | purpose | created_at | updated_at |
|------|------------|------|--------|----------|--------------|--------|--------|-------|---------|------------|------------|
| `express_checkout_events` | `01_express_checkout` | `raw` | `MergeTree` | `(timestamp, user_id, device_type)` | `toYYYYMM(timestamp)` | | | event | Raw Express events | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `express_otp_stats_daily` | `01_express_checkout` | `aggregate` | `SummingMergeTree` | `(day, device_type, destination)` | `toYYYYMM(day)` | | | day×device×dest | Daily OTP rates | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `mv_express_otp_daily` | `01_express_checkout` | `mv` | | | | `express_checkout_events` | `express_otp_stats_daily` | | Fills daily agg | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |

**Rule:** query `aggregate` / `raw` for data; use `mv.target`, don’t query the MV for facts.

---

### 3. `meta_events`

**Use:** Event → table + funnel order.

| feature_id | event_name | object_name | funnel_stage | sample_count | run_id | created_at | updated_at |
|------------|------------|-------------|--------------|--------------|--------|------------|------------|
| `01_express_checkout` | `express_checkout_shown` | `express_checkout_events` | `1` | `1500` | `a1b2…` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `01_express_checkout` | `otp_entered` | `express_checkout_events` | `4` | `910` | `a1b2…` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |

---

### 4. `meta_fields`

**Use:** Columns / paths per event.

| feature_id | event_name | field_path | column_name | inferred_type | null_rate | in_events | created_at | updated_at |
|------------|------------|------------|-------------|---------------|-----------|-----------|------------|------------|
| `01_express_checkout` | `otp_entered` | `otp_success` | `otp_success` | `UInt8` | `0.0` | `true` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `01_express_checkout` | `otp_entered` | `otp_channel` | `otp_channel` | `LowCardinality(String)` | `0.12` | `true` | `2026-06-10 09:00:00+00` | `2026-06-10 09:00:00+00` |

---

## Context (Context Agent)

### 5. `context_versions`

**Use:** Version pointer. Conversation uses `is_current = true`.

| context_version | parent_version | source | feature_id | is_current | summary | created_at | updated_at |
|-----------------|----------------|--------|------------|------------|---------|------------|------------|
| `v0` | | `seed` | | `false` | From `base_context.md` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `v3` | `v2` | `instrumentation` | `01_express_checkout` | `true` | Express + OTP↔K1 | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

All tables below are scoped by `context_version` (copy-forward on publish, or SCD — pick one in code).

---

### 6. `context_entities`

**Use:** Business entity definitions.

| context_version | entity_key | definition | primary_id_field | created_at | updated_at |
|-----------------|------------|------------|------------------|------------|------------|
| `v3` | `user` | Traveller on Atlys | `user_id` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `application` | Created at application_started | `application_id` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

### 7. `context_metrics`

**Use:** Metric formulas and caveats.

| context_version | metric_key | formula | grain | computable | caveats | created_at | updated_at |
|-----------------|------------|---------|-------|------------|---------|------------|------------|
| `v3` | `funnel_conversion` | purchase_completed users / application_started users | `user` | `true` | Leadership may use sessions — see contradictions | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `express_otp_success_rate` | otp_success=1 / otp_entered | `event` | `true` | Cut by device_type / os (K1) | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

### 8. `context_joins`

**Use:** How tables link (`join_keys` as plain text, comma-separated).

| context_version | from_table | to_table | join_keys | notes | created_at | updated_at |
|-----------------|------------|----------|-----------|-------|------------|------------|
| `v3` | `application_started` | `document_uploaded` | `application_id` | Empty before start | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `express_checkout_events` | `purchase_completed` | `application_id,user_id` | Express vs standard pay | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

### 9. `context_funnels` + `context_funnel_steps`

**Use:** Named funnels and ordered steps (no arrays/JSON).

| context_version | funnel_key | feature_id | created_at | updated_at |
|-----------------|------------|------------|------------|------------|
| `v3` | `pre_purchase` | | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `express_checkout` | `01_express_checkout` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

| context_version | funnel_key | step_order | step_name | created_at | updated_at |
|-----------------|------------|------------|-----------|------------|------------|
| `v3` | `pre_purchase` | `1` | `destination_card_clicked` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `pre_purchase` | `2` | `application_started` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `express_checkout` | `4` | `otp_entered` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

### 10. `context_known_issues`

**Use:** Product quirks (K1–K7, …).

| context_version | issue_id | title | analytic_hook | created_at | updated_at |
|-----------------|----------|-------|---------------|------------|------------|
| `v3` | `K1` | iOS WebKit OTP autofill | OTP/pay → purchase on iOS, Gulf geos | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `K6` | SUMMER20 coupon | Higher coupon_applied, lower value | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

### 11. `context_contradictions`

**Use:** Conflicting definitions to surface, not hide.

| context_version | contradiction_key | left_claim | right_claim | status | guidance | created_at | updated_at |
|-----------------|-------------------|------------|-------------|--------|----------|------------|------------|
| `v3` | `conversion_denominator` | purchases / sessions | purchases / application_started | `open` | State which denominator you used | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `eta_field_name` | visa_issuance_eta_days | eta_shown (DDL) | `open` | Prefer DDL column | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

## Flow

```
Instrumentation → CH + meta_objects / meta_events / meta_fields
Context        → bump context_versions + fill relational context_* rows
Conversation   → is_current version → SELECT context_* → aggregate in CH
```

## Conversation read

1. `context_versions` where `is_current`  
2. Load entities / metrics / joins / funnel steps / issues / contradictions for that version  
3. Prefer `meta_objects.kind = 'aggregate'`, else `raw`
