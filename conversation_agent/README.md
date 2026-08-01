# Conversation Agent

Analytics / PM conversation layer: answers product questions using **ClickHouse aggregates**, the **metadata registry**, and the **latest context** — then returns insight summaries a PM would act on (why, segment, recommendation).

Parent overview: [`../README.md`](../README.md)

## Role in the system

```
meta_* registry + fact tables + context_version
        │
        ▼
  Conversation Agent
        │
        ├── discover dimensions via registry
        ├── run CH funnels / group-bys
        ├── interpret aggregates (not raw rows)
        └── PM insight summary (+ confidence)
                │
                └── Langfuse: SQL, context_version, caveats
```

This layer is the contest “Analytics Agent” delivered as a conversational insight interface.

## Inputs / outputs

| | |
|--|--|
| **In** | Instrumented + existing tables, `meta_*` registry, current context from Context Agent, PM questions from `spec.md` |
| **Out** | Insight summary (why + segment + recommendation), confidence/caveats, Langfuse trace citing `context_version` |

## Rules

- [ ] Discover available dimensions/metrics via `meta_*` first, then query fact tables
- [ ] Push computation into ClickHouse (`uniq`, `windowFunnel`, `sequenceMatch`, group-bys); LLM interprets **aggregates only**
- [ ] Always cut by `device_type`, `geoip_country_code`, and `destination` before concluding
- [ ] Link findings to known issues in context (K1–K7) when relevant
- [ ] Answer the PM questions listed in each `spec.md`
- [ ] Include confidence / caveats (sample size, seasonality, coupon campaigns)
- [ ] Cite `context_version` and registry snapshot in the Langfuse trace

## Query preferences

```sql
-- Funnel stages (prefer CH helpers over dumping rows)
SELECT windowFunnel(86400)(
  timestamp,
  event = 'destination_card_clicked',
  event = 'application_started',
  event = 'document_uploaded',
  event = 'purchase_completed'
) AS level
FROM ...
GROUP BY user_id;

SELECT uniqExact(user_id)
FROM application_started
WHERE timestamp BETWEEN ... AND ...;
```

Always filter a time window and segment by device / geo / destination.

### Registry-first discovery

```sql
SELECT field_path, column_name, inferred_type, null_rate
FROM meta_field_registry FINAL
WHERE feature_id = {feature}
  AND in_events = 1
  AND null_rate < 0.5;
```

## Insight shape (target output)

For each finding:

1. **What** — metric / funnel step change (numbers from CH)  
2. **Where** — device × geo × destination cut  
3. **Why** — hypothesis linked to context (K-issue, coupon, seasonality, schema caveat)  
4. **Do** — concrete PM recommendation  
5. **Confidence** — sample size, data quality, metric-definition conflicts from Context  

## Specs to support

| # | Feature | Example analytic focus |
|---|---------|------------------------|
| 01 | Express Checkout | OTP success, latency, vs standard `pay_now` / purchase path |
| 02 | Group / Family | group size, drop on traveller add/remove, submit rate |
| 03 | Status Sharing | channel mix, recipient new-user CTA |
| 04 | Abandoned Checkout Recovery | drop_step, reminder → reconvert lift |
| 05 | Instant Forex | offer → purchase, FX pair / addon value |

Day-2 unseen sixth spec must use the **same** path (no one-off hand analysis without a trace).

## Hard constraints

- Do not dump raw event rows into the LLM context
- Do not use stale context — always pull latest from Context Agent
- Every SQL tool call and interpretation step goes to Langfuse

## Related

- Schemas + registry: [`../instrumentation_agent/README.md`](../instrumentation_agent/README.md)
- Living context / K1–K7: [`../context_agent/README.md`](../context_agent/README.md)
- Query patterns: [`.cursor/skills/clickathon-agenthouse/reference.md`](../.cursor/skills/clickathon-agenthouse/reference.md)
