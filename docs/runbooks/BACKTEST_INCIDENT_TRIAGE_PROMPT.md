# BACKTEST INCIDENT TRIAGE PROMPT

One-page runbook for triaging backtests that run for 6h+, crash, or get terminated by runtime enforcement.

**Last Updated:** 2026-01-22  
**Status:** Draft  
**Audience:** Developers, AI Agents, BotOps  

## Overview

Backtests should be **fast** and **reliable**. When a backtest incident happens:
- Do **not** “fix” or edit user strategy code to resolve incidents.
- Fix the platform: LumiBot library, Data Downloader, BotManager, and any routing/orchestration layers.

**Security**
- Never paste production secrets into docs, issues, or PRs.
- Do not hardcode private endpoints; use placeholders and env vars.

## What “good” looks like (acceptance criteria)

- A backtest should not run for hours due to preventable platform issues (data routing, stuck loops, wedged downloader).
- If the runtime-enforcement system terminates a backtest, the UI status must be updated correctly (no “stuck backtesting”).
- When a backtest crashes or is terminated, the system must record enough context to debug and permanently fix the root cause:
  - identifiers (bot_id / manager_bot_id, revision_id if available)
  - runtime cap configuration used at the time
  - last ~50 lines of logs (or a stable “tail” excerpt)
  - a pointer to the exact executed code (S3 key / artifact pointer), not only a human screenshot


## Canonical workflow (human or AI)

### 1) Collect evidence (do this before changing anything)

For a given `manager_bot_id` / `bot_id`:
- Runtime + lifecycle: ECS task timings (createdAt, startedAt, stoppedAt) and total wall time.
- Logs: capture **the last ~50 lines** and also “signature lines” (timeouts, empty data, retry loops).
- Data-source signature:
  - Identify whether the run is calling Theta via Data Downloader queue (look for `Submitted to queue:` / `Submit network timeout`)
  - Identify symbol/type mismatches (e.g., index vs stock endpoints, 24/7 vs equity session windows).
- Strategy metadata (without editing strategy):
  - `datasource_class` used
  - asset universe and asset types (INDEX/STOCK/CRYPTO/OPTION/FUTURES)
  - timeframe/cadence (minute/hour/day)

### 2) Classify incident by root-cause “signature”

Common high-signal signatures and likely owners:

- **Downloader queue submit timeouts** (`Submit network timeout`, `Read timed out`):
  - Primary owner: Data Downloader reliability (queue DB growth, stuck endpoints, health checks, self-heal).
  - Secondary owner: platform routing (don’t route a workload to a provider that’s not healthy; ensure retries recover after self-heal).

- **Empty / invalid historical data for a symbol** (e.g. `No OHLC data returned for NDX ...`):
  - Primary owner: vendor symbol mapping / correct endpoint / asset-type routing.
  - Secondary owner: LumiBot data-layer behavior that “spins” instead of progressing once data is available.

- **24/7 assets treated like equities** (e.g. crypto returning only ~16h of minute bars instead of 24h):
  - Primary owner: LumiBot calendar/session logic for CRYPTO + provider routing.
  - Secondary owner: data provider capabilities (which provider supplies 24/7 data).

- **Status stuck after termination** (UI still shows `backtesting` after ECS task ended):
  - Primary owner: BotManager runtime-enforcement stop path (must update status via authenticated API).
  - Secondary owner: BotManager status reconciliation (Dynamo vs ECS mismatch repair).

### 3) Fix the root cause (platform-only; do not edit user strategy code)

General rules:
- Prefer fixes in shared libraries and routing (LumiBot + downloader + BotManager) so **all** strategies benefit.
- Avoid “papering over” the problem with earlier failures; make the system resilient and able to complete.
- If a provider truly cannot supply required data, the platform must route to a provider that can (without proxy substitution like NDX→QQQ).

### 4) Verify with a controlled reproduction

- Reproduce with the exact `manager_bot_id` inputs when possible (same date range, same symbols, same provider).
- Confirm the fix changes behavior:
  - fewer retries / no infinite loops
  - progress continues during data hydration
  - completion updates status + artifacts


## Recommended incident record schema (for BotManager to write)

Store incidents in a dedicated table (example name: `${env}-backtest-incidents`).

Required fields:
- `incident_id` (UUID) or composite PK (`bot_id` + `created_at_unix`)
- `bot_id` / `manager_bot_id`
- `event_type` (`runtime_enforced_stop`, `crash`, `failed`, `completed_with_errors`)
- `runtime_cap_seconds` (store the *configured* cap at the time; do not hardcode “6h”)
- `stop_method` (API stop vs direct ECS stop, if relevant)
- `ecs_task_arn` (if known)
- `status_before` / `status_after`
- `log_tail` (last ~50 lines)
- `code_pointer` (S3 key/URL or content-addressed hash pointer)
- `metadata` (optional): `revision_id`, `strategy_name`, `datasource_class`, `symbols`, `timestep`, `provider`

Notes:
- DynamoDB item size is limited; store large code blobs in S3 and keep only a pointer + hash in DynamoDB.
- If revision metadata is not currently available in BotManager, add it to the backtest submission payload (BotSpot → BotManager) as non-secret metadata.


## System prompt template (for an “incident triage agent”)

Use this as the fixed instruction header when automating incident analysis.

### Prompt

You are investigating a long-running or failed backtest incident. Your goals:
1) Identify the root cause for the incident using logs + code + platform behavior.
2) Propose a permanent fix in platform code (LumiBot / Data Downloader / BotManager / provider routing).
3) Do NOT modify user strategy code to “make it pass”.
4) Do NOT propose “fail fast” as a substitute for reliability. Prefer self-heal and correct routing so backtests complete.
5) If the incident is due to incorrect symbol/asset-type routing, fix routing/mapping so the requested symbol works as intended (no proxy substitutions like NDX→QQQ).

Required output:
- Incident summary: what happened, where it stalled, and why.
- Evidence: the exact log signatures and code paths that prove the root cause.
- Fix plan: specific files/components to change, plus how to verify the fix.
- Follow-ups: what to add to incident recording so future cases are easier.
