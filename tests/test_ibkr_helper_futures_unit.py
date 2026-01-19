from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumibot.entities import Asset


def test_ibkr_helper_future_requires_expiration(monkeypatch, tmp_path):
    import lumibot.tools.ibkr_helper as ibkr_helper

    monkeypatch.setattr(ibkr_helper, "LUMIBOT_CACHE_FOLDER", tmp_path.as_posix())

    def fake_queue_request(url: str, querystring, headers=None, timeout=None):
        raise AssertionError(f"Should not attempt remote calls for invalid futures asset: {url}")

    monkeypatch.setattr(ibkr_helper, "queue_request", fake_queue_request)

    asset = Asset(symbol="MES", asset_type="future")
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 1, 1, 0, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="futures require an explicit expiration"):
        ibkr_helper.get_price_data(asset=asset, quote=None, timestep="minute", start_dt=start, end_dt=end)


def test_ibkr_helper_future_applies_contract_multiplier_and_min_tick(monkeypatch, tmp_path):
    import lumibot.tools.ibkr_helper as ibkr_helper

    monkeypatch.setattr(ibkr_helper, "LUMIBOT_CACHE_FOLDER", tmp_path.as_posix())

    class _StubCache:
        def ensure_local_file(self, path, payload=None):
            return

        def on_local_update(self, path, payload=None):
            return

    monkeypatch.setattr(ibkr_helper, "get_backtest_cache", lambda: _StubCache())
    monkeypatch.setattr(ibkr_helper, "_resolve_conid", lambda *, asset, quote, exchange: 999)
    monkeypatch.setattr(ibkr_helper, "_fetch_contract_info", lambda conid: {"multiplier": "5", "minTick": "0.25"})

    asset = Asset(symbol="MES", asset_type=Asset.AssetType.FUTURE, expiration=datetime(2025, 12, 19).date())
    assert asset.multiplier == 1
    assert getattr(asset, "min_tick", None) is None

    ibkr_helper._maybe_apply_future_contract_metadata(asset=asset, exchange="CME")

    assert asset.multiplier == 5
    assert getattr(asset, "min_tick", None) == pytest.approx(0.25, rel=1e-12)

    cache_file = tmp_path / "ibkr" / "future" / "contracts" / "CONID_999.json"
    assert cache_file.exists()


def test_ibkr_helper_resolve_conid_accepts_usd_key_for_futures(monkeypatch, tmp_path):
    import json
    from datetime import date

    import lumibot.tools.ibkr_helper as ibkr_helper

    monkeypatch.setattr(ibkr_helper, "LUMIBOT_CACHE_FOLDER", tmp_path.as_posix())

    class _StubCache:
        def ensure_local_file(self, path, payload=None):
            return

        def on_local_update(self, path, payload=None):
            return

    monkeypatch.setattr(ibkr_helper, "get_backtest_cache", lambda: _StubCache())

    def _fail_lookup(*, asset, quote, exchange):  # noqa: ANN001
        raise AssertionError("Should not call remote conid lookup when a cached USD-key exists")

    monkeypatch.setattr(ibkr_helper, "_lookup_conid_remote", _fail_lookup)

    conids_path = tmp_path / "ibkr" / "conids.json"
    conids_path.parent.mkdir(parents=True, exist_ok=True)
    conids_path.write_text(json.dumps({"future|MES|USD|CME|20251219": 730283085}), encoding="utf-8")

    asset = Asset(symbol="MES", asset_type=Asset.AssetType.FUTURE, expiration=date(2025, 12, 19))
    assert ibkr_helper._resolve_conid(asset=asset, quote=None, exchange="CME") == 730283085
