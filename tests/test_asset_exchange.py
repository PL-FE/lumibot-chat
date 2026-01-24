from lumibot.entities import Asset


def test_asset_accepts_exchange_kwarg():
    asset = Asset("NQ", Asset.AssetType.CONT_FUTURE, exchange="CME")
    assert asset.exchange == "CME"


def test_asset_exchange_is_normalized():
    asset = Asset("NQ", Asset.AssetType.CONT_FUTURE, exchange="cme")
    assert asset.exchange == "CME"


def test_asset_exchange_affects_equality_and_hash():
    asset_1 = Asset("NQ", Asset.AssetType.CONT_FUTURE, exchange="CME")
    asset_2 = Asset("NQ", Asset.AssetType.CONT_FUTURE, exchange="CME")
    asset_3 = Asset("NQ", Asset.AssetType.CONT_FUTURE, exchange="CBOT")

    assert asset_1 == asset_2
    assert asset_1 != asset_3
    assert hash(asset_1) == hash(asset_2)
    assert hash(asset_1) != hash(asset_3)


def test_asset_exchange_defaults_to_none_and_roundtrips():
    asset = Asset("NQ", Asset.AssetType.CONT_FUTURE)
    serialized = asset.to_dict()
    restored = Asset.from_dict(serialized)

    assert restored.exchange is None
    assert restored == asset
