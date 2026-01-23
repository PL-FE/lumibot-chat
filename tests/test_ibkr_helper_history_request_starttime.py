from __future__ import annotations

from datetime import datetime, timezone

import pytest


def test_ibkr_history_request_formats_starttime_in_lumibot_timezone(monkeypatch):
    """Regression test for IBKR history pagination gaps.

    IBKR Client Portal's `startTime` is interpreted in the account/session timezone (commonly
    America/New_York). Formatting UTC here can create DST-sized gaps when we page in 1000-point
    chunks (4h in summer, 5h in winter), which then causes stale-bar execution during backtests.
    """
    import lumibot.tools.ibkr_helper as ibkr_helper
    from lumibot.constants import LUMIBOT_DEFAULT_PYTZ

    monkeypatch.setenv("DATADOWNLOADER_BASE_URL", "http://localhost:8080")

    captured = {}

    def fake_queue_request(*, url, querystring, headers=None, timeout=None):
        captured["url"] = url
        captured["query"] = dict(querystring)
        return {}

    monkeypatch.setattr(ibkr_helper, "queue_request", fake_queue_request)

    start_time_utc = datetime(2025, 10, 30, 13, 39, 0, tzinfo=timezone.utc)
    expected = start_time_utc.astimezone(LUMIBOT_DEFAULT_PYTZ).strftime("%Y%m%d-%H:%M:%S")

    ibkr_helper._ibkr_history_request(
        conid=123,
        period="10min",
        bar="1min",
        start_time=start_time_utc,
        exchange="CME",
        include_after_hours=True,
        continuous=False,
        source="Trades",
    )

    assert captured["query"]["startTime"] == expected
    assert captured["query"]["outsideRth"] == "true"

