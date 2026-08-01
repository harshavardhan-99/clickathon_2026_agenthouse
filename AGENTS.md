# AGENTS.md — Click-a-thon 2026 AgentHouse

This repository is a **ClickHouse + multi-agent analytics** hackathon package (Atlys / synthetic data).

## Orient immediately

1. Read `.cursor/rules/clickathon-stack.mdc` (always-on stack summary).
2. Follow the project skill `.cursor/skills/clickathon-agenthouse/SKILL.md` for build workflow.
3. Canonical challenge docs: `problem_statement.md`, `readme_start_here.md`, `base_context.md`.

## What you are building

Three agents (Instrumentation, Analytics, Context) + Langfuse tracing + a light visualization layer. Primary datastore is **ClickHouse Cloud**. Feature specs live under `specs/`; existing tables under `data/`.

## Before querying data

If `data/*.parquet` files are ~133 bytes, they are Git LFS pointers — run `git lfs pull`, then `data/load.sh` against your ClickHouse service.

## Do not

- Assume `base_context.md` is fully consistent with `data/ddl.sql`
- Reuse legacy `ORDER BY (id, …)` for newly designed tables
- Pull raw event rows into an LLM for analysis — aggregate in ClickHouse first
- Hand-write Day-2 sixth-spec outputs without a matching agent trace
