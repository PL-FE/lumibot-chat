# IBKR Futures Backtesting (REST) — CME Equity Index Futures

This document describes LumiBot’s Interactive Brokers **Client Portal (REST)** backtesting path for **CME equity index futures** (example: ES/MES/NQ/MNQ).

## Scope (Phase 3)

- **Supported (v1):** CME equity index futures (ES/MES/NQ/MNQ) via IBKR REST historical bars.
- **Not in scope (v1):** other futures venues/products (energy/metals/ag), tick-level / second-level history guarantees, and live-trading behavior changes.
- **Backtesting only:** the primary data path is IBKR Client Portal (REST) via the Data Downloader.
  - **TWS is not used for bar history in normal backtests.**
  - A **one-time TWS/Gateway backfill** is used only to populate the expired-futures conid registry
    (see `docs/investigations/2026-01-18_IBKR_EXPIRED_FUTURES_CONID_BACKFILL.md`).

## Data Path (where the bars come from)

1. LumiBot backtesting requests historical bars through `lumibot/tools/ibkr_helper.py`.
2. `ibkr_helper` calls the **Data Downloader** proxy route:
   - `GET {DATADOWNLOADER_BASE_URL}/ibkr/iserver/marketdata/history`
3. The Data Downloader forwards the request to the **Client Portal Gateway** sidecar (IBeam).

The entire stack is cache-backed:
- Local Parquet cache under `LUMIBOT_CACHE_FOLDER/ibkr/...`
- Optional S3 mirroring through the standard `LUMIBOT_CACHE_*` settings (see `docs/ENV_VARS.md`).

## Contract Requirements (expiration + metadata)

### Futures contracts

IBKR futures bar history requires a specific contract identifier (conid). LumiBot resolves conids and caches them under:
- `LUMIBOT_CACHE_FOLDER/ibkr/conids.json`

For deterministic acceptance and correct lookup behavior, **explicit futures** should be used:
- `Asset("MES", asset_type="future", expiration=date(2025, 12, 19))`

### Expired contracts (critical)

IBKR Client Portal cannot reliably discover conids for **expired** futures. For backtests that reference expired
contracts (or for `cont_future` stitching over expired months), LumiBot relies on a pre-populated conid registry:

- `ibkr/conids.json` (S3-mirrored)

See: `docs/investigations/2026-01-18_IBKR_EXPIRED_FUTURES_CONID_BACKFILL.md`.

### Multiplier + minTick (mandatory for correct PnL and tick rounding)

For realistic futures accounting:
- **PnL uses multiplier** (e.g., MES multiplier = 5)
- **SMART_LIMIT tick rounding** must respect the exchange tick size (e.g., MES minTick = 0.25)

LumiBot populates these via the IBKR contract info endpoint (cached):
- `GET /ibkr/iserver/contract/{conid}/info`
- cached at `LUMIBOT_CACHE_FOLDER/ibkr/future/contracts/CONID_<conid>.json`

## Intraday bars (minute/hour)

Futures backtesting uses **Trades OHLC** bars as the candle series.

By default, futures fills are intended to be **OHLC/TRADES-based** (to be comparable to DataBento’s OHLCV backtests).

Optional quote-based behavior (SMART_LIMIT / buy-at-ask sell-at-bid) can be enabled by deriving bid/ask from
`Bid_Ask` + `Midpoint` history sources, but this is intentionally **disabled by default** because it multiplies request
volume and reintroduces Client Portal history flakiness:

- Enable explicitly: `LUMIBOT_IBKR_ENABLE_FUTURES_BID_ASK=1`

## “Last price” semantics (no lookahead)

For futures/continuous futures in backtests, LumiBot treats `get_last_price(dt)` as **the last completed bar’s close**
(not the current minute’s open). This avoids implicit lookahead at bar boundaries and makes parity comparisons more
stable (especially around the daily maintenance gap and weekend reopen).

Implementation detail:
- `InteractiveBrokersRESTBacktesting.get_last_price()` evaluates the series at `dt - 1µs` for `future`/`cont_future`.

### End-of-window tolerance (avoids repeated downloader retries)

IBKR history can omit the final bar(s) near a requested window boundary (commonly 1–3 bars). To keep deterministic
acceptance runs stable (and avoid hammering the downloader), LumiBot treats cache coverage within a small tolerance
as “good enough” and does not attempt to fetch beyond it.

### Closed-session gaps (weekends/holidays)

Futures windows can begin/end inside long closed intervals (weekends/holidays). LumiBot treats *fully closed* intervals
at the start/end of the requested window as “already satisfied” by the cache and does not attempt to fetch those bars.

## Daily bars (session-aligned, not midnight)

Futures “daily” in LumiBot must align to the **`us_futures`** market session, not midnight:
- many futures strategies use `self.set_market("us_futures")`
- the backtesting clock advances based on that calendar

LumiBot derives futures daily bars by aggregating intraday bars per `pandas_market_calendars.get_calendar("us_futures")`, indexing each daily bar at the **session close** timestamp.

## Continuous futures (synthetic roll schedule)

For `Asset(asset_type="cont_future")`, IBKR REST backtesting follows LumiBot’s **synthetic** roll schedule:
- resolves a sequence of explicit contracts over the requested window using `lumibot/tools/futures_roll.py`
- fetches each contract’s Trades OHLC bars and stitches them into a continuous series

This matches the semantics used by Tradovate/ProjectX (live) and DataBento (backtesting), and is also the basis for the
IBKR-vs-DataBento parity suite (`docs/IBKR_DATABENTO_FUTURES_PARITY.md`).

### Roll-boundary stitching (one-minute overlap)

Because futures backtests use “last completed bar” semantics for `get_last_price()`, the minute immediately preceding a
roll boundary must exist in the stitched series for the **new** contract (so the previous-close lookup at the roll
timestamp is well-defined).

IBKR cont-futures stitching therefore widens each post-first segment by **1 minute on the left** and relies on stable
de-duping so the newer contract overrides overlaps deterministically.

## Deterministic Acceptance Backtests (how we keep this stable)

Acceptance backtests are deterministic and enforce a **warm S3 cache invariant**:
- runs must not submit downloader queue requests
- headline tearsheet metrics are asserted strictly

Acceptance harness:
- `tests/backtest/test_acceptance_backtests_ci.py`

IBKR extension notes:
- IBKR REST backtesting also routes through `queue_request()`, and the telemetry is recorded under
  `thetadata_queue_telemetry` in `*_settings.json`.
- For IBKR acceptance, we therefore assert:
  - `thetadata_queue_telemetry.submit_requests == 0`

See also:
- `docs/ACCEPTANCE_BACKTESTS.md`
- `docsrc/backtesting.ibkr.rst`

## Live broker alignment (Tradovate / ProjectX)

The acceptance and backtesting design target is: **match live trading behavior**.

Operationally:
- **Tradovate** is the primary live futures broker.
- **ProjectX** is expected to behave the same at the strategy semantics level.
- IBKR live trading may require explicit contracts (root + expiration); acceptance uses explicit contracts for determinism.
