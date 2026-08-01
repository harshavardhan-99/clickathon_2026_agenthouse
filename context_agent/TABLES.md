# Context Agent — Postgres tables

Living **meta catalog** + **business context** for Atlys. All of these live in **Postgres**.  
ClickHouse holds event facts, aggregate tables, MVs, and views; Postgres only **describes** them.

**Write path:** Instrumentation Agent calls Context Agent → upsert meta → reconcile/publish context.  
**Read path:** Conversation Agent reads latest `context_version` + meta, then queries ClickHouse.

**Common columns:** every table includes `created_at` and `updated_at` (`TIMESTAMPTZ`).

```
features
 └── meta_ingest_runs
 └── meta_table_registry      (raw / aggregate tables)
 └── meta_view_registry       (materialized views / normal views)
 └── meta_event_registry
      └── meta_field_registry

context_versions
 ├── context_snapshots
 ├── context_entities
 ├── context_metrics
 ├── context_joins
 ├── context_funnels
 ├── context_known_issues
 └── context_contradictions
```

---

## 1. `features`

**Use:** Catalog of product features / specs.

| feature_id | name | spec_path | status | created_at | updated_at |
|------------|------|-----------|--------|------------|------------|
| `01_express_checkout` | Express Checkout | `specs/01_express_checkout/spec.md` | `instrumented` | `2026-06-08 10:00:00+00` | `2026-06-08 12:00:00+00` |
| `pre_purchase_funnel` | Core pre-purchase funnel | `base_context.md` | `active` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |

---

## 2. `meta_ingest_runs`

**Use:** One row per Instrumentation → Context call (idempotency + audit).

| run_id | feature_id | status | context_version_out | created_at | updated_at |
|--------|------------|--------|---------------------|------------|------------|
| `a1b2c3…` | `01_express_checkout` | `success` | `v3` | `2026-06-08 12:00:00+00` | `2026-06-08 12:01:00+00` |
| `d4e5f6…` | `01_express_checkout` | `success` | `v4` | `2026-06-10 09:00:00+00` | `2026-06-10 09:01:00+00` |

*(Second run = new field discovered, e.g. `otp_channel`.)*

---

## 3. `meta_table_registry`

**Use:** ClickHouse objects that **store data** (raw event tables + aggregate / rollup tables).

| table_name | feature_id | object_kind | engine | order_by | partition_by | grain | stores_data | created_at | updated_at |
|------------|------------|-------------|--------|----------|--------------|-------|-------------|------------|------------|
| `express_checkout_events` | `01_express_checkout` | `raw` | `MergeTree` | `(timestamp, user_id, device_type)` | `toYYYYMM(timestamp)` | event row | `true` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `express_otp_stats_daily` | `01_express_checkout` | `aggregate` | `SummingMergeTree` | `(day, device_type, destination)` | `toYYYYMM(day)` | day × device × destination | `true` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |

---

## 4. `meta_view_registry`

**Use:** Materialized views (pipes into a target table) and normal views (saved SQL, no storage).

| view_name | view_type | source_tables | target_table | stores_data | purpose | created_at | updated_at |
|-----------|-----------|---------------|--------------|-------------|---------|------------|------------|
| `mv_express_otp_daily` | `materialized_view` | `{express_checkout_events}` | `express_otp_stats_daily` | `false` | On insert, roll OTP success into daily agg table | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `v_express_checkout_funnel` | `view` | `{express_checkout_events}` | `null` | `false` | Convenience SELECT for Express funnel stages | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |

**Rule for Conversation:** query the **target aggregate table**, not the MV itself; use a normal view only as a SQL helper.

---

## 5. `meta_event_registry`

**Use:** Event name → ClickHouse table + funnel stage.

| feature_id | event_name | target_table | funnel_stage | kind | created_at | updated_at |
|------------|------------|--------------|--------------|------|------------|------------|
| `01_express_checkout` | `express_checkout_shown` | `express_checkout_events` | `1` | `feature` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `01_express_checkout` | `otp_entered` | `express_checkout_events` | `4` | `feature` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |

---

## 6. `meta_field_registry`

**Use:** Fields / columns per event (including new fields over time).

| feature_id | event_name | field_path | column_name | inferred_type | is_envelope | in_events | created_at | updated_at |
|------------|------------|------------|-------------|---------------|-------------|-----------|------------|------------|
| `01_express_checkout` | `otp_entered` | `otp_success` | `otp_success` | `UInt8` | `false` | `true` | `2026-06-08 12:00:00+00` | `2026-06-08 12:00:00+00` |
| `01_express_checkout` | `otp_entered` | `otp_channel` | `otp_channel` | `LowCardinality(String)` | `false` | `true` | `2026-06-10 09:00:00+00` | `2026-06-10 09:00:00+00` |

*(Second row = field that appeared later; Instrumentation altered CH + Context upserted meta.)*

---

## 7. `context_versions`

**Use:** Each published version of the living context. Conversation pins insights to one version.

| context_version | parent_version | source | feature_id | is_current | summary | created_at | updated_at |
|-----------------|----------------|--------|------------|------------|---------|------------|------------|
| `v0` | `null` | `seed` | `null` | `false` | Seeded from `base_context.md` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `v3` | `v2` | `instrumentation` | `01_express_checkout` | `true` | Express meta + OTP↔K1 link | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

## 8. `context_snapshots`

**Use:** Full JSON payload for “get latest context” in one read.

| context_version | body (sketch) | created_at | updated_at |
|-----------------|---------------|------------|------------|
| `v0` | `{ "entities": [...], "metrics": [...], "funnels": ["pre_purchase"], "issues": ["K1"…"K7"] }` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `v3` | `{ …same…, "features": ["01_express_checkout"], "funnels": ["pre_purchase", "express_checkout"] }` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

## 9. `context_entities`

**Use:** What business objects mean.

| entity_key | definition (short) | primary_id_field | created_at | updated_at |
|------------|--------------------|------------------|------------|------------|
| `user` | Traveller on Atlys; may browse many destinations | `user_id` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `application` | One visa application; created at `application_started` | `application_id` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |

---

## 10. `context_metrics`

**Use:** Metric formulas, grain, and caveats.

| metric_key | formula (short) | grain | computable | caveats | created_at | updated_at |
|------------|-----------------|-------|------------|---------|------------|------------|
| `funnel_conversion` | `purchase_completed` users ÷ `application_started` users | `user` | `true` | Funnel dashboards use this denominator | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `express_otp_success_rate` | `otp_success=1` ÷ `otp_entered` | `event` | `true` | Cut by `device_type` / `os` (see K1) | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

## 11. `context_joins`

**Use:** How tables link for journey analysis.

| from_table | to_table | join_keys | notes | created_at | updated_at |
|------------|----------|-----------|-------|------------|------------|
| `application_started` | `document_uploaded` | `{application_id}` | Empty before application start | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `express_checkout_events` | `purchase_completed` | `{application_id, user_id}` | Compare Express vs standard pay path | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

## 12. `context_funnels`

**Use:** Ordered funnel definitions (core + per feature).

| funnel_key | feature_id | steps (ordered) | created_at | updated_at |
|------------|------------|-----------------|------------|------------|
| `pre_purchase` | `null` | `destination_card_clicked` → `application_started` → `document_uploaded` → `purchase_completed` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `express_checkout` | `01_express_checkout` | `shown` → `selected` → `saved_method` → `otp_entered` → `express_payment_confirmed` | `2026-06-08 12:01:00+00` | `2026-06-08 12:01:00+00` |

---

## 13. `context_known_issues`

**Use:** Product quirks Conversation should cite when interpreting numbers.

| issue_id | title | analytic_hook | created_at | updated_at |
|----------|-------|---------------|------------|------------|
| `K1` | iOS WebKit OTP autofill regression | Watch OTP / pay → purchase on iOS, Gulf geos | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `K6` | SUMMER20 coupon campaign | Elevated `coupon_applied`, lower realised `value` | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |

---

## 14. `context_contradictions`

**Use:** Conflicting definitions — surface them; do not silently pick one.

| contradiction_key | left_claim | right_claim | status | guidance_for_analytics | created_at | updated_at |
|-------------------|------------|-------------|--------|------------------------|------------|------------|
| `conversion_denominator` | Leadership: purchases ÷ **sessions** | Funnel dashboards: purchases ÷ **application_started** | `open` | State which denominator you used | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |
| `eta_field_name` | Context prose: `visa_issuance_eta_days` | DDL: `eta_shown` (String) | `open` | Prefer DDL column; note type mismatch | `2026-04-01 00:00:00+00` | `2026-04-01 00:00:00+00` |

---

## Conversation read recipe

1. Current version from `context_versions` (`is_current = true`).  
2. Snapshot (and/or relational rows) for meaning.  
3. `meta_*` for tables / events / fields / views.  
4. Prefer **aggregate tables** when grain matches; else raw.  
5. Query **ClickHouse** for aggregates only; cite `context_version` in the insight output.
