import datetime
from lumibot.backtesting import YahooDataBacktesting
from lumibot.example_strategies.stock_buy_and_hold import BuyAndHold

bt_start = datetime.datetime(2023, 1, 1)
bt_end = datetime.datetime(2023, 6, 1)

results, strategy = BuyAndHold.run_backtest(
    datasource_class=YahooDataBacktesting,
    backtesting_start=bt_start,
    backtesting_end=bt_end,
    budget=100000,
    benchmark_asset="SPY",
    show_plot=False,
    analyze_backtest=True,
    quiet_logs=True
)

import pprint
print("--- Results ---")
print(type(results))
print("--- Strategy Stats ---")
print("Has _stats?:", hasattr(strategy, '_stats'))
print("Has stats?:", hasattr(strategy, 'stats'))
stats = getattr(strategy, 'stats', getattr(strategy, '_stats', None))
if stats is not None:
    print("type:", type(stats))
    print("Columns/Keys:", getattr(stats, 'columns', getattr(stats, 'keys', lambda: None)()))
    print(stats.head() if hasattr(stats, 'head') else "No head()")
else:
    print("No stats attribute.")

print("Does the broker have history?")
import pandas as pd
if hasattr(strategy, 'broker'):
    history = strategy.broker.get_portfolio_history()
    print("broker history type:", type(history))
    if hasattr(history, 'columns'):
        print(history.columns)
