from __future__ import annotations

import pytest

from lumibot.backtesting.routed_backtesting import RoutedBacktestingPandas
from lumibot.entities import Asset


def test_routed_backtesting_accepts_polygon_provider_in_json_mapping():
    routing = RoutedBacktestingPandas._normalize_routing(
        {
            "default": "thetadata",
            "crypto": "polygon",
        }
    )
    rb = RoutedBacktestingPandas.__new__(RoutedBacktestingPandas)
    rb._routing = routing  # type: ignore[attr-defined]

    asset = Asset("BTC", asset_type=Asset.AssetType.CRYPTO)
    assert rb._provider_for_asset(asset) == "polygon"


def test_routed_backtesting_rejects_unknown_provider():
    with pytest.raises(ValueError):
        RoutedBacktestingPandas._normalize_routing({"default": "thetadata", "crypto": "nope"})

