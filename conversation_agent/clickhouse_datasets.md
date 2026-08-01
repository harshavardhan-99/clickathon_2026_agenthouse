# Atlys ClickHouse datasets

Live snapshot from ClickHouse Cloud (`atlys`), server `26.2.1`.

## Connection

| Setting | Value |
|--------|--------|
| Database | `atlys` |
| Data window | `2025-12-31` → `2026-07-01` |

## Funnel

```
destination_card_clicked → application_started → document_uploaded → purchase_completed
```

Join on `user_id` (whole journey) and `application_id` (from `application_started` onward). Order by `timestamp`.

Supporting (not funnel steps): `search_typed`, `landing_page_scrolled`, `auth_completed`, `pay_now_clicked`.

## Segment dimensions

Cut by these before concluding:

- `device_type` — `ios`, `android`, `web-user-b2c`, `Desktop`
- `geoip_country_code`
- `destination` — top purchases: `AE`, `US`, `ID`, `TH`, `VN`, …

## Shared envelope (all tables)

`id`, `timestamp`, `user_id`, `application_id`, `app_session_id`, `device`, `device_type`, `os`, `app_version`, `client_lib`, `geoip_country_code`, `geoip_subdivision_1_code`, `city`, `client_ip`, `latitude`, `longitude`, `locale`, `language`, `funnel_type`, `co_travelers`, `is_guest`, `is_referral`, `is_enterprise`, `gclid`, `fbclid`, `gad_source`, `citizenship`, `destination`, `is_back_filled`, `duplicate_id`

## Tables

| Table | Kind | Rows | Users | Event columns | Notes |
|-------|------|------|-------|---------------|-------|
| `destination_card_clicked` | funnel | 1,000,000 | 1,000,000 | `visa_type`, `card_type`, `page_version`, `flow`, `is_guest_browse` | Top of funnel; `application_id` usually empty |
| `application_started` | funnel | 154,413 | 154,413 | `purpose`, `eta_shown`, `flow` | Creates `application_id` |
| `document_uploaded` | funnel | 20,446 | 20,446 | `doc_type`, `capture_mode`, `scan_mode`, `retry_count`, `failed_attempt_threshold`, `is_crossed_failed_attempt_threshold` | Capture quality signals |
| `purchase_completed` | funnel | 7,054 | 7,054 | `value`, `currency`, `coupon_applied`, `coupon_name`, `discount_amount`, `insurance_added`, `insurance_amount`, `plan_selected` | Conversion / revenue |
| `search_typed` | supporting | 599,630 | 599,630 | `search_term`, `results_count`, `source` | Discovery; noisy |
| `landing_page_scrolled` | supporting | 499,786 | 499,786 | `scroll_depth_pct`, `time_on_page_s`, `page_version` | Engagement depth |
| `auth_completed` | supporting | 183,790 | 183,790 | `auth_method`, `is_new_user`, `attempts` | Login/signup |
| `pay_now_clicked` | supporting | 14,739 | 14,739 | `payment_method`, `amount`, `currency`, `coupon_applied`, `plan_selected` | Click ≠ pay |

## Query rules

- Aggregate in ClickHouse (`uniq`, `group by`, `windowFunnel`) — never dump raw event rows
- Always filter a time window
- Prefer `atlys.<table>` fully qualified names
