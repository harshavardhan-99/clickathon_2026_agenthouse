# Schema context (legacy reference)

Conversation **discover_schema** uses context catalog tools only.
This file is a static reminder of the physical SAS — not injected into the agent.

## Table

`atlys.activity_events`

| Column | Notes |
|--------|--------|
| `id` | Event id |
| `timestamp` | DateTime — `windowFunnel` / time filters |
| `event_name` | Event name — funnel conditions |
| `user_id` | Journey partition |
| `application_id` | From `application_started` onward |
| `device_type` | Segment |
| `os` | Segment |
| `geoip_country_code` | Segment |
| `destination` | Segment |
| `event_info` | JSON payload |

## Core funnel

```
destination_card_clicked → application_started → document_uploaded → purchase_completed
```
