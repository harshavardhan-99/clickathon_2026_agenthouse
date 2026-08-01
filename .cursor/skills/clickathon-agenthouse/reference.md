# AgentHouse reference

Detail for Instrumentation / Analytics. Prefer sampling NDJSON over memorizing this file.

## Existing schema quirks (`data/ddl.sql`)

- All 8 tables: `MergeTree`, `PARTITION BY toYYYYMM(timestamp)`, `ORDER BY (id, timestamp, user_id)`.
- Wide Nullable columns; empty strings and nulls common.
- `os` messy (Android rows may have `os = NULL` while `device_type = 'android'`).
- `device_type` values include: `ios`, `android`, `web-user-b2c`, `Desktop`.
- `duplicate_id` / `is_back_filled` mark re-ingested rows — filter for clean funnels when needed.
- Context prose vs DDL: context mentions `visa_issuance_eta_days`; DDL has `eta_shown Nullable(String)`.

## Metric definitions (suspect — Context Agent should reconcile)

From `base_context.md`:

- Leadership conversion = purchases ÷ **sessions**
- Funnel dashboards = `purchase_completed` users ÷ `application_started` users
- Drop-off = 1 − (users at N+1 ÷ users at N), distinct `user_id`, ordered stages
- Passport pass rate = uploads with `is_crossed_failed_attempt_threshold = 0` ÷ uploads
- On-time delivery = post-purchase (not in these tables)

## Known issues (K1–K7) — use in insight narratives

| ID | Issue | Analytic hook |
|----|-------|----------------|
| K1 | iOS WebKit OTP autofill | pay_now / express OTP → purchase on iOS, Gulf geos |
| K2 | Passport model update Apr 2026 | Android capture failures |
| K3 | MRZ OCR non-Latin | higher `retry_count` |
| K4 | Schengen summer scarcity | seasonal softness, not product bug |
| K5 | WhatsApp nudge Feb 2026 | return-to-funnel lifts |
| K6 | SUMMER20 coupon | higher `coupon_applied`, lower `value` |
| K7 | App 7.45.x rollout | funnel timing shifts |

## Spec event field hints

### 01 Express Checkout

Events: `express_checkout_shown`, `express_checkout_selected`, `saved_method_used`, `otp_entered`, `express_payment_confirmed`.

Notable fields: `eligible`, `shown_amount`, `currency`, `saved_method_type`, `otp_attempts`, `otp_success`, nested `payment` (`amount`, `currency`, `latency_ms`).

Compare to standard path via existing `pay_now_clicked` / `purchase_completed`.

### 02 Group / Family

Events: `group_started`, `traveller_added`, `traveller_removed`, `group_submitted`.

Notable: `group_id`, `group_size`, `traveller_index`, `relation`, `docs_complete`, `travellers_submitted`.

### 03 Status Sharing

Events: `share_clicked`, `channel_selected`, `link_generated`, `link_opened`, `recipient_cta_clicked`.

Notable: `status_shared`, `channel`, `share_id`, `recipient_is_new_user`, `cta`. Recipient events keyed by `share_id`.

### 04 Abandoned Checkout Recovery

Events: `abandonment_detected`, `reminder_sent`, `reminder_opened`, `reminder_cta_clicked`, `resumed_at_step`, `reconverted`.

Notable: `drop_step` (funnel stage names), `channel`, `hours_since_drop`. Cross-check abandon rates against existing funnel tables.

### 05 Instant Forex

Events: `forex_offer_shown`, `currency_selected`, `amount_entered`, `forex_added_to_cart`, `forex_purchased`.

Notable: `from_currency`, `to_currency`, `fx_rate`, `amount`, `addon_value_inr`.

## ClickHouse query preferences for Analytics

```sql
-- Funnel stages (prefer CH funnel helpers over dumping rows)
SELECT windowFunnel(86400)(
  timestamp,
  event = 'destination_card_clicked',
  event = 'application_started',
  event = 'document_uploaded',
  event = 'purchase_completed'
) AS level
FROM ...
GROUP BY user_id;

-- Distinct users per stage
SELECT uniqExact(user_id) FROM application_started
WHERE timestamp BETWEEN ... AND ...;
```

Always filter a time window and cut by `device_type` / `geoip_country_code` / `destination`.

## Day-2 unseen spec checklist

- [ ] Same Instrumentation path as specs 01–05 (no hand-written DDL without trace)
- [ ] Analytics insight in product language
- [ ] Context updated and version referenced in Analytics trace
- [ ] Langfuse (or equivalent) chain exported / linked in submission
