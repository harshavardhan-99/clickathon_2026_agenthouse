# Context Agent — Postgres tables (minimal)

**4 tables + optional audit.** JSONB used for flexible payloads. Same functionality: discover CH objects/fields, versioned meaning, core funnel, feature funnel, issues/contradictions.

| Writer | Tables |
|--------|--------|
| Instrumentation | `meta_objects`, `meta_events`, `meta_fields` (+ optional `instrumentation_runs`) |
| Context | `context_versions`, `context_items` |
| Conversation | read-only |

Every table: `created_at`, `updated_at`. No `langfuse_trace_id`.

```
meta_objects
meta_events              ← feature funnel = funnel_stage
 └── meta_fields

context_versions
 └── context_items       ← entity | metric | join | funnel_step | issue | contradiction
```

---

## Meta

### 1. `meta_objects`

ClickHouse catalog. `kind` = `raw` \| `aggregate` \| `mv` \| `view`.

| name | feature_id | kind | order_by | partition_by | source | target | purpose | created_at | updated_at |
|------|------------|------|----------|--------------|--------|--------|---------|------------|------------|
| `express_checkout_events` | `01_express_checkout` | `raw` | `(timestamp, user_id, device_type)` | `toYYYYMM(timestamp)` | | | Raw events | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `express_otp_stats_daily` | `01_express_checkout` | `aggregate` | `(day, device_type, destination)` | `toYYYYMM(day)` | | | Daily OTP | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `mv_express_otp_daily` | `01_express_checkout` | `mv` | | | `express_checkout_events` | `express_otp_stats_daily` | Fills agg | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |

---

### 2. `meta_events`

Event → table. **Feature funnel = `funnel_stage`** (not copied into context).

| feature_id | event_name | object_name | funnel_stage | sample_count | created_at | updated_at |
|------------|------------|-------------|--------------|--------------|------------|------------|
| `01_express_checkout` | `express_checkout_shown` | `express_checkout_events` | `1` | `1500` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `01_express_checkout` | `otp_entered` | `express_checkout_events` | `4` | `910` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |

---

### 3. `meta_fields`

| feature_id | event_name | field_path | column_name | inferred_type | null_rate | example_values | created_at | updated_at |
|------------|------------|------------|-------------|---------------|-----------|----------------|------------|------------|
| `01_express_checkout` | `otp_entered` | `otp_success` | `otp_success` | `UInt8` | `0.0` | `[1,0]` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `01_express_checkout` | `otp_entered` | `otp_channel` | `otp_channel` | `LowCardinality(String)` | `0.12` | `["sms","email"]` | `2026-06-10 09:00:00+00` | `2026-06-10 09:00:00+00` |

---

## Context

### 4. `context_versions`

| context_version | parent_version | source | feature_id | is_current | summary | created_at | updated_at |
|-----------------|----------------|--------|------------|------------|---------|------------|------------|
| `v0` | | `seed` | | `false` | From `base_context.md` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `v3` | `v2` | `instrumentation` | `01_express_checkout` | `true` | Express + OTP↔K1 | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

### 5. `context_items`

**One table** for all meaning. `kind` = `entity` \| `metric` \| `join` \| `funnel_step` \| `issue` \| `contradiction`.

| context_version | kind | item_key | label | payload | created_at | updated_at |
|-----------------|------|----------|-------|---------|------------|------------|
| `v3` | `entity` | `user` | Traveller | `{"primary_id_field":"user_id","definition":"Traveller on Atlys"}` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `metric` | `funnel_conversion` | Funnel conversion | `{"formula":"purchase_completed / application_started","grain":"user","caveats":"Leadership may use sessions"}` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `join` | `app_to_doc` | | `{"from":"application_started","to":"document_uploaded","keys":["application_id"],"notes":"Empty before start"}` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `funnel_step` | `pre_purchase:1` | | `{"funnel_key":"pre_purchase","step_order":1,"step_name":"destination_card_clicked"}` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `funnel_step` | `pre_purchase:2` | | `{"funnel_key":"pre_purchase","step_order":2,"step_name":"application_started"}` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `issue` | `K1` | iOS WebKit OTP autofill | `{"hook":"OTP/pay → purchase on iOS"}` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |
| `v3` | `contradiction` | `conversion_denominator` | | `{"left":"purchases/sessions","right":"purchases/application_started","guidance":"State denominator"}` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

**Core funnel only** as `funnel_step` rows. Feature funnels → `meta_events.funnel_stage`.

---

## Optional

`instrumentation_runs` — audit only; not required for Conversation.

---

## Conversation read

1. Current `context_versions`  
2. `context_items` for that version (`WHERE kind = …` as needed)  
3. Feature funnel: `meta_events ORDER BY funnel_stage`  
4. Prefer `meta_objects` where `kind = 'aggregate'`, else `raw`
