# Environment Variables (Engineering Notes)

This page documents environment variables used by LumiBot, with an emphasis on **backtesting** and **ThetaData / downloader / caching** behavior.

**Public docs (source of truth):** the Sphinx page at `docsrc/environment_variables.rst` must be updated whenever env var behavior changes.

## Rules

- **Never commit secrets.** Document variable *names*, accepted values, and semantics—never real API keys, tokens, passwords, or AWS secrets.
- **Env var changes require docs changes.** If you add/change an env var, update:
  - `docsrc/environment_variables.rst` (public docs), and
  - this file (engineering notes) when it helps contributors.

## Backtesting selection + dates

### `IS_BACKTESTING`
- Purpose: Signals backtesting mode for certain code paths.
- Values: `True` / `False` (string).

### `BACKTESTING_START` / `BACKTESTING_END`
- Purpose: Default date range used by `Strategy.run_backtest()` / `Strategy.backtest()` when dates are not passed in code.
- Format: `YYYY-MM-DD`

### `BACKTESTING_DATA_SOURCE`
- Purpose: Selects the backtesting datasource **even if code passes an explicit `datasource_class`**.
- Values (case-insensitive):
  - `thetadata`, `yahoo`, `polygon`, `alpaca`, `ccxt`, `databento`
  - `none` to disable env override and rely on code.
- Where: `lumibot/strategies/_strategy.py` datasource selection logic.

## Backtest output + UX flags

### `SHOW_PLOT`, `SHOW_INDICATORS`, `SHOW_TEARSHEET`
- Purpose: Enables/disables artifact generation.
- Values: `True` / `False` (string).

### `BACKTESTING_QUIET_LOGS`
- Purpose: Reduce log noise during backtests.
- Values: `true` / `false` (string).

### `BACKTESTING_SHOW_PROGRESS_BAR`
- Purpose: Enable progress bar updates.
- Values: `true` / `false` (string).

## Trade audit telemetry (NVDA/SPX accuracy audits)

### `LUMIBOT_BACKTEST_AUDIT`
- Purpose: Emit **per-fill audit telemetry** into the trades/event CSV as `audit.*` columns.
- Values: `1` enables (anything truthy); unset/`0` disables.
- Output:
  - `*_trades.csv` / trade-event CSV contains additional `audit.*` columns.
  - Includes quote/bid/ask snapshots (asset + underlying for options), bar OHLC, SMART_LIMIT inputs, and multileg linkage.
- Where:
  - Audit collection: `lumibot/backtesting/backtesting_broker.py`
  - Audit column emission: `lumibot/brokers/broker.py`

## Profiling (parity + performance investigations)

### `BACKTESTING_PROFILE`
- Purpose: Enable profiling during backtests to attribute time (S3 IO vs compute vs artifacts).
- Values:
  - `yappi` (supported)
- Output: produces a `*_profile_yappi.csv` artifact alongside other backtest artifacts.
- Related tooling: `scripts/analyze_yappi_csv.py`

## Remote downloader (ThetaData via shared service)

### `DATADOWNLOADER_BASE_URL`
- Purpose: Points LumiBot at the remote downloader service.
- Example: `http://data-downloader.lumiwealth.com:8080`

### `DATADOWNLOADER_API_KEY` / `DATADOWNLOADER_API_KEY_HEADER`
- Purpose: Authentication for the downloader service.
- Values: **do not document actual values**; they must be supplied by the runtime environment.

### `DATADOWNLOADER_SKIP_LOCAL_START`
- Purpose: Prevents any local downloader/ThetaTerminal bootstrap logic from running (backtests must use the remote downloader in production workflows).

## Remote cache (S3)

### `LUMIBOT_CACHE_BACKEND` / `LUMIBOT_CACHE_MODE`
- Purpose: Enable remote cache mirroring.
- Common values:
  - `LUMIBOT_CACHE_BACKEND=s3`
  - `LUMIBOT_CACHE_MODE=readwrite` (or `readonly`)

### `LUMIBOT_CACHE_FOLDER`
- Purpose: Override the local cache folder (useful to simulate a fresh ECS task).
- Notes: This is read at import/startup time; changing it mid-run will not relocate already-created paths.

### `LUMIBOT_CACHE_S3_BUCKET`, `LUMIBOT_CACHE_S3_PREFIX`, `LUMIBOT_CACHE_S3_REGION`
- Purpose: S3 target configuration.

### `LUMIBOT_CACHE_S3_VERSION`
- Purpose: Namespace/version the remote cache without deleting anything.
- Practical use: set a unique version to simulate a “cold S3” run safely.

### `LUMIBOT_CACHE_S3_ACCESS_KEY_ID`, `LUMIBOT_CACHE_S3_SECRET_ACCESS_KEY`, `LUMIBOT_CACHE_S3_SESSION_TOKEN`
- Purpose: Credentials for S3 access when not using an instance/task role.
- Values: **never commit**.

For cache key layout and validation workflow, see `docs/remote_cache.md`.

