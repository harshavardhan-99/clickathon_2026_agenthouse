# Schema context

Database: `atlys` (ClickHouse Cloud).

## Funnel table — use this

**Always query `atlys.funnel_events`.** Do not use per-event tables or a bare
`events` table for funnel analytics.

| Table | Kind | Role |
|-------|------|------|
| `funnel_events` | funnel | One row per funnel event; filter / condition on the event name column |

Qualify as `atlys.funnel_events`.

### Event names in `funnel_events` (core funnel)

- `destination_card_clicked`
- `application_started`
- `document_uploaded`
- `purchase_completed`

Funnel order:

```
destination_card_clicked → application_started → document_uploaded → purchase_completed
```

### Shared / analysis columns

| Column | Notes |
|--------|--------|
| `timestamp` | DateTime — use for `windowFunnel` and time filters |
| `event` | Event name (string) — use in `windowFunnel` conditions |
| `user_id` | Whole-journey partition key |
| `application_id` | From `application_started` onward |
| `device_type` | Segment |
| `os` | Segment |
| `geoip_country_code` | Segment |
| `destination` | Segment |
| `funnel_type` | Segment |
| `step` | Optional UInt funnel position when present |

## Primary keys for analysis

- **User journey:** `user_id`
- **Application journey:** `application_id`
- **Event time:** `timestamp`
