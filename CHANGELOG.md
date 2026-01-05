# Changelog

## 4.4.25 - 2026-01-04

Deploy marker: `b7f83088` ("Deploy 4.4.25")

### Added
- Public documentation page for environment variables (`docsrc/environment_variables.rst`) plus engineering notes (`docs/ENV_VARS.md`).
- Backtest audit telemetry can be preserved in a separate `*_trade_events.csv` artifact (see `LUMIBOT_BACKTEST_AUDIT`).
- Investigation docs for ThetaData corporate actions and performance.

### Changed
- ThetaData option chain defaults are now bounded to reduce cold-cache request fanout (configurable via `THETADATA_CHAIN_DEFAULT_MAX_DAYS_OUT*`).

### Fixed
- OptionsHelper delta-to-strike selection fast path to prevent per-strike quote storms (SPX Copy2/Copy3 slowness).
- Prevent backtest tear sheet generation from crashing on degenerate/flat returns (NVDA end-of-run failures).
- Reduce ThetaData corporate action request thrash via memoization/negative caching.
- Normalize ThetaData intraday bars for corporate actions in backtests so option strikes and underlying prices stay in the same split-adjusted space (NVDA split issues).
- Improve ThetaData snapshot quote selection near the session open to avoid missing NBBO due to end-of-minute timestamps.

## 4.3.6 - 2024-11-16

- Fixed ThetaData EOD corrections by fetching a real 09:30–09:31 minute window for each trading day, preventing zero-length requests and the resulting terminal hangs.
- Logged the active downloader base URL whenever remote mode is enabled to make it obvious in backtest logs which data path is being used.
- Added regression tests covering the custom session window override plus the fallback path when Theta rejects an invalid minute range.
