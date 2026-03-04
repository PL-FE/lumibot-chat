from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.example_strategies.stock_buy_and_hold import BuyAndHold
import os
import glob

results, strategy = BuyAndHold.run_backtest(
    datasource_class=YahooDataBacktesting,
    backtesting_start=datetime(2023, 1, 1),
    backtesting_end=datetime(2023, 6, 1),
    budget=100000,
    benchmark_asset="SPY",
    show_plot=False,
    save_tearsheet=True,
    show_tearsheet=False,
    analyze_backtest=True,
    quiet_logs=True
)
print("Finished. Logs dir contents:")
logs_dirs = glob.glob(os.path.join("logs", "*"))
print(logs_dirs)
if logs_dirs:
    latest = max(logs_dirs, key=os.path.getmtime)
    print("Latest:", latest)
    print("Inside latest:", glob.glob(os.path.join(latest, "*")))
