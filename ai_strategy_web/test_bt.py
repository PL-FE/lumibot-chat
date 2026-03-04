import requests
import json
import time

url = "http://localhost:5001/api/backtest"
payload = {
    "code": """from lumibot.strategies.strategy import Strategy

class BuyAndHold(Strategy):
    parameters = {
        "buy_symbol": "SPY",
    }
    
    def initialize(self):
        self.sleeptime = "1D"
    
    def on_trading_iteration(self):
        buy_symbol = self.parameters["buy_symbol"]
        current_price = self.get_last_price(buy_symbol)
        
        all_positions = self.get_positions()
        if len(all_positions) == 0:
            quantity = int(self.get_portfolio_value() / current_price)
            if quantity > 0:
                order = self.create_order(buy_symbol, quantity, "buy")
                self.submit_order(order)
""",
    "start_date": "2023-01-01",
    "end_date": "2023-06-01",
    "budget": 100000,
    "benchmark": "SPY"
}

res = requests.post(url, json=payload)
data = res.json()
print("Submit:", data)

task_id = data.get("task_id")
if task_id:
    while True:
        status_res = requests.get(f"http://localhost:5001/api/backtest/status/{task_id}")
        st = status_res.json()
        print(st["status"], st.get("progress_msg"))
        if st["status"] in ["done", "error"]:
            break
        time.sleep(1)
        
    if st["status"] == "done":
        result_res = requests.get(f"http://localhost:5001/api/backtest/result/{task_id}")
        r = result_res.json()
        print("Result:", r["result"])
        if r.get("chart_b64"):
            print("Chart b64 generated, length:", len(r["chart_b64"]))
        else:
            print("NO CHART!")
