# Context Agent

Maintains the **living business context layer**: entity definitions, metric semantics, join maps, and known issues — refreshed whenever Instrumentation adds tables or registry rows, and always served fresh to the Conversation (analytics) agent.

Parent overview: [`../README.md`](../README.md) (architecture + **`uv sync`** local setup).

> **Status:** design-only. Hosted on the same FastAPI + Agno AgentOS app as the other agents; context snapshots land in **Postgres**.

## Role in the system

```
base_context.md (suspect) + DDL + Postgres meta_* registry
        │
        ▼
┌──────────────────────────────────────┐
│  FastAPI (hosts Agno AgentOS)        │
│  Context Agent                       │
│    reconcile → version snapshot → PG │
│    expose latest defs → Conversation │
└──────────────────────────────────────┘
```

Treat `base_context.md` as **intentionally imperfect**. Metric conflicts and naming drift vs `data/ddl.sql` are part of the challenge — surface them; don’t silently paper over them.

## Inputs / outputs

| | |
|--|--|
| **In** | `base_context.md`, existing + new DDL, `meta_event_registry` / `meta_field_registry` / `meta_schema_decisions` |
| **Out** | Versioned living context in **Postgres** (`context_snapshots`), contradiction log, join map |

## Must do

- [ ] Auto-update when Instrumentation adds tables/columns (hook on registry / schema changelog)
- [ ] Feed Conversation the **latest** context (no stale snapshot)
- [ ] Surface contradictions (e.g. conversion denominator: sessions vs `application_started`; `eta_shown` in DDL vs `visa_issuance_eta_days` in prose)
- [ ] Keep entity join map current — prefer envelope columns from `meta_field_registry`
- [ ] Record `context_version` so Analytics traces can cite it

## Metric definitions to reconcile

From `base_context.md` (validate against DDL + events):

| Metric | Claimed definition | Watch for |
|--------|--------------------|-----------|
| Leadership conversion | purchases ÷ **sessions** | May conflict with funnel dashboards |
| Funnel conversion | `purchase_completed` users ÷ `application_started` users | Different denominator than leadership |
| Drop-off | 1 − (users at N+1 ÷ users at N), distinct `user_id` | Stage ordering must match registry |
| Passport pass rate | uploads with `is_crossed_failed_attempt_threshold = 0` ÷ uploads | Null / backfill rows |
| On-time delivery | post-purchase | Not in these event tables |

## Known issues (K1–K7) — keep in context for insight narratives

| ID | Issue | Analytic hook |
|----|-------|----------------|
| K1 | iOS WebKit OTP autofill | pay_now / express OTP → purchase on iOS, Gulf geos |
| K2 | Passport model update Apr 2026 | Android capture failures |
| K3 | MRZ OCR non-Latin | higher `retry_count` |
| K4 | Schengen summer scarcity | seasonal softness, not product bug |
| K5 | WhatsApp nudge Feb 2026 | return-to-funnel lifts |
| K6 | SUMMER20 coupon | higher `coupon_applied`, lower `value` |
| K7 | App 7.45.x rollout | funnel timing shifts |

## Suggested storage shape

Justify the choice in Langfuse; common options:

1. **ClickHouse table** `context_snapshots(version, updated_at, body, source_hash)` — queryable, versioned with warehouse  
2. **Markdown / JSON file** in-repo for human review + CH mirror for agents  
3. Optional **embeddings** for retrieval — only if it improves Conversation quality without hiding contradictions

Minimum viable: versioned document + join map derived from registry envelope fields.

## Join map (funnel cheat sheet)

- `user_id` — whole journey  
- `application_id` — from `application_started` onward  
- Order events by `timestamp`  
- Filter `duplicate_id` / `is_back_filled` when clean funnels matter  

Existing tables (context must stay aligned as new feature tables land):

| Table | Kind |
|-------|------|
| destination_card_clicked → application_started → document_uploaded → purchase_completed | funnel |
| search_typed, landing_page_scrolled, auth_completed, pay_now_clicked | supporting |

## Related

- Upstream registry: [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- Downstream insights: [`../conversation_agent/README.md`](../conversation_agent/README.md)
