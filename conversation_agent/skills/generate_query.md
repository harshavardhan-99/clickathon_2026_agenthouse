---
name: clickhouse-funnel-analytics
description: >-
  Build product-analytics funnels from atlys.funnel_events using windowFunnel(),
  and shape the result for the visualization agent. Use whenever the user asks
  for conversion funnels, drop-off analysis, step-by-step completion rates, or
  "how many users went from X to Y". Also use for segment cuts
  (device/os/geo/destination) of a funnel.
---

# ClickHouse Funnel Analytics

Generates funnel data with `windowFunnel()` against **`atlys.funnel_events`**, then
hands a normalized result to the visualization agent. **Read this whole file
before writing a query.**

**Input to this step:** `VizSpec` JSON. Map VizSpec → one `QuerySpec`.

## 1. Table — CRITICAL

**Always use `atlys.funnel_events`.** Do **not** query `events`, and do **not**
UNION per-event tables for funnels.

One row per funnel event. Key columns:

- `timestamp` — DateTime (seconds) for `windowFunnel` and time filters
- `event` — event name string (e.g. `application_started`, `purchase_completed`)
- `user_id`, `application_id`, `device_type`, `os`, `geoip_country_code`, `destination`, …

Partition key is usually `user_id` (use `group_id` / `share_id` when those columns
exist and VizSpec calls for group/share funnels).

## 2. windowFunnel — mechanics and gotchas

```sql
windowFunnel(window, [mode, ...])(timestamp, cond1, cond2, ..., condN)
```

- **`window`'s unit matches the timestamp column's granularity.** `DateTime` →
  seconds. State the unit in a SQL comment on every query.
- Returns deepest **level** per entity (`1..N`). Per-step reach =
  `countIf(level >= k)`. Conversion from start = `reached_k / reached_1`.
- Pass conditions in **funnel order** using `event = '…'`.
- Default mode allows interleaved events — don't add `strict_order` unless asked.
- Use `'strict_increase'` if equal timestamps can mis-order steps.
- Companion metrics (latency, AOV, K-factor) are **not** inside `windowFunnel` —
  note in `caveats`; this step still emits one funnel SQL.

### Base funnel template (conversion by device)

```sql
-- window: 86400 = 24h, since timestamp is DateTime (seconds)
WITH funnel_levels AS (
    SELECT
        user_id,
        any(device_type) AS device_type,
        windowFunnel(86400)(
            timestamp,
            event = 'application_started',
            event = 'purchase_completed'
        ) AS level
    FROM atlys.funnel_events
    WHERE timestamp >= now() - INTERVAL 30 DAY
      AND timestamp < now()
    GROUP BY user_id
)
SELECT
    device_type,
    countIf(level >= 1) AS entities_step_1,
    countIf(level >= 2) AS entities_step_2,
    countIf(level >= 2) / nullIf(countIf(level >= 1), 0) AS conversion_from_start
FROM funnel_levels
GROUP BY device_type
ORDER BY device_type
```

Prefer a final SELECT with `step_name`, `entities`, `conversion_from_start`
(and a segment column when cut) so the viz layer can map to §5.

### Segmented funnel

Keep the segment via `any(device_type)` (or first-event device) in the inner
`GROUP BY user_id`, then group by that segment in the outer query.

## 3. Core funnel steps

| Partition key | Steps (`event` in order) | Suggested window |
|---------------|--------------------------|------------------|
| `user_id` | `destination_card_clicked` → `application_started` → `document_uploaded` → `purchase_completed` | 86400 |

Other feature funnels (Express, Group, Status Sharing, …) use the same table when
those `event` values are present — still **`FROM atlys.funnel_events` only**.

## 4. Metrics alongside the funnel

Latency, AOV/quantiles, churn, K-factor → second query / `caveats` only.

## 5. Output contract for the visualization agent

```json
{
  "funnel": "core_purchase_conversion",
  "window_seconds": 86400,
  "filters": {"start_date": "...", "end_date": "...", "segment": "device_type"},
  "steps": [
    {"step": "application_started", "entities": 12000, "conversion_from_start": 1.0},
    {"step": "purchase_completed", "entities": 700, "conversion_from_start": 0.058}
  ],
  "segments": null
}
```

**Your `QuerySpec` must:**

1. `sql` — one `SELECT` / `WITH … SELECT` with **`FROM atlys.funnel_events`** only.
2. Fill `funnel`, `window_seconds`, `step_names`, `filters`.
3. Prefer columns: `step`/`step_name`, `entities`, `conversion_from_start`
   (+ segment column when cut).
4. `tables_used` = `["funnel_events"]`; `caveats` for assumptions.

## 6. QuerySpec output

Return **only** `QuerySpec` JSON. No markdown fences inside the `sql` string.
