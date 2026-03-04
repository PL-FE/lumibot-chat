import os
import datetime
import pytz

# Simulate what frontend passes
api_key = "O_XNvY3VOvwGZ5Impa6qKaszL0W3XLg2"
os.environ["POLYGON_API_KEY"] = api_key

from lumibot.backtesting import PolygonDataBacktesting
from lumibot.strategies.strategy import Strategy

class SimplePolygonStrategy(Strategy):
    parameters = {"symbol": "SPY"}
    def initialize(self):
        self.sleeptime = "1D"
    def on_trading_iteration(self):
        symbol = self.parameters["symbol"]
        price = self.get_last_price(symbol)
        self.log_message(f"Hello polygon SPY price: {price}")
        self.buy(symbol, 1)

tz = pytz.timezone("America/New_York")
bt_start = tz.localize(datetime.datetime(2022, 1, 1))
bt_end   = tz.localize(datetime.datetime(2022, 1, 5))

print("Starting backtest...")
results, strat = SimplePolygonStrategy.run_backtest(
    datasource_class=PolygonDataBacktesting,
    backtesting_start=bt_start,
    backtesting_end=bt_end,
    budget=100000,
    benchmark_asset="SPY",
    show_plot=False,
    show_tearsheet=False,
    save_tearsheet=False,
    polygon_api_key=api_key,
    quiet_logs=False,
)
print("Finished!")
