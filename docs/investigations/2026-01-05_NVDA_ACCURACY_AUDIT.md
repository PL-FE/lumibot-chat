# 2026-01-05 — NVDA Accuracy Audit + Crash Root Cause (manager_bot_id=334e2c98-7134-4f38-860c-b6b11879a51b)

## Scope

- Strategy code (read-only repro): `/Users/robertgrzesik/Documents/Development/Strategy Library/tmp/backtest_code/334e2c98-7134-4f38-860c-b6b11879a51b/main.py`
- Engine: LumiBot (local prod-faithful backtests)
- Data provider: ThetaData via remote downloader
- Cache backend: S3 (`LUMIBOT_CACHE_BACKEND=s3`)

## Goals

- **P0 (prod crash):** explain and eliminate the “ERROR_CODE_CRASH with no traceback” failure mode.
- **Performance:** warm-cache runs should be fast (no runaway refetch loops).
- **Accuracy:** produce a full “MELI-style” audit table for every trade-event with maximum telemetry.

## Root Cause: missing-day detection used UTC dates (after-hours spillover)

### Symptom

Backtests would repeatedly report:

- `Using forward-filled price ... (no current price available)`
- `prefetch_complete but coverage insufficient ...` + `refreshing cache ... reasons=end`
- **But no downloader request was enqueued for the missing trading day**, so the cached dataset stayed stale.

In practice this manifested as **every other trading day missing** for intraday stock OHLC:

- ET trading days present: **Feb 3 + Feb 5**
- But UTC calendar days present: **Feb 3 + Feb 4 + Feb 5 + Feb 6**
  - because **Feb 3 after-hours** (19:xx ET) is **Feb 4 UTC**, and similarly for Feb 5 → Feb 6 UTC.

### Why it happened

ThetaData intraday caches are stored with **UTC timestamps** and (by default) include extended-hours bars.

`thetadata_helper.get_missing_dates()` historically computed cached coverage using:

- `df.index.date` (UTC calendar days)

This caused the after-hours bars to “leak” into the next UTC day, so the cache looked like it already covered the next trading day and **skipped downloading it**.

That led to:

- missing intraday OHLC for alternating market days,
- lots of forward-filled prices,
- and long-running backtests (and in production, a likely ECS OOM/exit without a Python traceback, reported as `ERROR_CODE_CRASH`).

### Fix (LumiBot)

Commit: `5dda5002` — `Fix ThetaData missing-day detection across UTC midnights`

- In `lumibot/tools/thetadata_helper.py`, compute missing-day coverage using the **market-local date** (convert index to `LUMIBOT_DEFAULT_PYTZ` before taking `.date`).
- Regression test: `tests/test_thetadata_missing_dates_market_timezone.py`

## Local Proof Run (audit-enabled)

This run is short but includes a real order and fill so the audit telemetry is concrete.

- Window: `2025-01-20 -> 2025-02-10`
- Workdir: `/Users/robertgrzesik/Documents/Development/backtest_runs/nvda_trade_audit_20260105_063026`
- Cache folder: `/Users/robertgrzesik/Documents/Development/tmp/lumibot_cache_nvda_trade_audit_20260105_063026`
- S3 cache version: `v1`
- Result: ✅ completed, tearsheet produced, and trade-event audit emitted.

### Audit artifact

- `docs/investigations/data/2026-01-05_nvda_trade_events_audit.csv`

### Trade-event highlights (human sanity check)

| dt (ET) | event | contract | qty | limit | fill | underlying px | notes |
|---|---|---|---:|---:|---:|---:|---|
| 2025-01-27 09:30 | submit | NVDA 2025-04-17 135C | 43 | 9.25 | — | 124.5658 | drawdown ≥ 5% triggered entry |
| 2025-01-27 09:30 | fill | NVDA 2025-04-17 135C | 43 | 9.25 | 9.25 | 124.5658 | fill model: OHLC limit logic |

## Notes / Next Steps

- A longer continuous run through **option expiry (2025-04-17)** is required to fully audit the lifecycle (expiry/exit behavior) in a single backtest run.
- Cold-cache hydrating runs can exceed a 20m leash; warm-cache proof runs should be much faster once S3 is fully hydrated for the full window.

