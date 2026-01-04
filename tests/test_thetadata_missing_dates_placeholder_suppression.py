from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd
import pytz

from lumibot.tools import thetadata_helper


def test_get_missing_dates_suppresses_placeholders_before_first_real_date(monkeypatch) -> None:
    """
    Regression test: do not refetch placeholder-only dates before the first real cached date.

    Why this matters:
    - Some strategies require lookback padding before BACKTESTING_START (e.g. SMA200).
    - For certain symbols/providers, the earliest part of that padding range may legitimately have
      no data ("pre-coverage"). We store placeholder rows to record this.
    - Re-fetching those placeholder-only pre-coverage days causes repeated downloader-queue usage,
      which breaks the warm-cache invariant and slows CI/local runs.
    """
    trading_dates = [date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 4)]
    monkeypatch.setattr(thetadata_helper, "get_trading_dates", lambda asset, start, end: trading_dates)

    asset = SimpleNamespace(symbol="TQQQ", asset_type="stock")
    idx = pd.to_datetime(
        [
            "2020-01-01 00:00:00+00:00",  # placeholder (pre-coverage)
            "2020-01-02 00:00:00+00:00",  # placeholder (pre-coverage)
            "2020-01-03 00:00:00+00:00",  # real cache begins here
            "2020-01-04 00:00:00+00:00",  # placeholder after first real date -> should refetch
        ],
        utc=True,
    )
    df_all = pd.DataFrame({"missing": [1, 1, 0, 1]}, index=idx)

    missing = thetadata_helper.get_missing_dates(
        df_all,
        asset,
        start=datetime(2020, 1, 1, tzinfo=pytz.UTC),
        end=datetime(2020, 1, 5, tzinfo=pytz.UTC),
    )

    assert missing == [date(2020, 1, 4)]


def test_get_missing_dates_skips_refetch_for_placeholder_only_cache(monkeypatch) -> None:
    """
    Regression test: if the cache is *placeholder-only* for a requested range, do not refetch.

    This situation occurs when ThetaData returns "no data found" for a contract/range and we record
    placeholders to make that absence explicit. Re-fetching the same placeholder-only range on
    every run causes repeated downloader-queue usage and breaks the warm-cache invariant.
    """
    trading_dates = [date(2025, 10, 1), date(2025, 10, 2)]
    monkeypatch.setattr(thetadata_helper, "get_trading_dates", lambda asset, start, end: trading_dates)

    asset = SimpleNamespace(symbol="STRL", asset_type="option")
    idx = pd.to_datetime(
        [
            "2025-10-01 00:00:00+00:00",
            "2025-10-02 00:00:00+00:00",
        ],
        utc=True,
    )
    df_all = pd.DataFrame({"missing": [1, 1]}, index=idx)

    missing = thetadata_helper.get_missing_dates(
        df_all,
        asset,
        start=datetime(2025, 10, 1, tzinfo=pytz.UTC),
        end=datetime(2025, 10, 3, tzinfo=pytz.UTC),
    )

    assert missing == []
