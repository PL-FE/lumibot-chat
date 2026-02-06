OptionsHelper
=============

``OptionsHelper`` is LumiBot's high-level helper for **options selection** (expirations, strikes, deltas) and **multi-leg order building/execution**.
For most options strategies, using ``OptionsHelper`` is both **more reliable** (avoids non-existent expiries/strikes during backtests) and **much faster** than brute-force approaches that scan large strike lists and call ``get_greeks()`` per strike.

Quickstart (delta-based strike)
--------------------------------

.. code-block:: python

   from datetime import timedelta
   from lumibot.entities import Asset
   from lumibot.components.options_helper import OptionsHelper

   def initialize(self):
       self.options_helper = OptionsHelper(self)

   def pick_20_delta_put(self):
       underlying = Asset("SPY", asset_type=Asset.AssetType.STOCK)
       chains = self.get_chains(underlying)
       if not chains:
           self.log_message("No option chains available", color="yellow")
           return None

       expiry = self.options_helper.get_expiration_on_or_after_date(
           self.get_datetime() + timedelta(days=0),
           chains,
           "put",
           underlying_asset=underlying,
       )
       if expiry is None:
           self.log_message("No valid expiry found", color="yellow")
           return None

       underlying_price = self.get_last_price(underlying)
       if underlying_price is None:
           self.log_message("Underlying price unavailable", color="yellow")
           return None

       strike = self.options_helper.find_strike_for_delta(
           underlying_asset=underlying,
           underlying_price=float(underlying_price),
           target_delta=-0.20,
           expiry=expiry,
           right="put",
       )
       return strike

Performance note
----------------

- Prefer ``OptionsHelper.find_strike_for_delta(...)`` over scanning strikes and calling ``get_greeks()`` repeatedly.
- If your strategy retries entry multiple times intraday, cache the selected expiry/strike in ``self.vars`` and only recompute when the underlying has moved materially.

API Reference
-------------

.. currentmodule:: lumibot.components.options_helper

.. autoclass:: OptionMarketEvaluation
   :members:

.. autoclass:: OptionsHelper
   :members:
   :member-order: bysource
