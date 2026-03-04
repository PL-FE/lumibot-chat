"""
阿里云百炼 AI 对话引擎
接入 qwen3.5-flash-2026-02-23 模型，通过系统提示词引导 AI 生成 lumibot 策略代码
"""

import os
from openai import OpenAI

# 阿里云百炼 API 配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-a48a13fcd7294622bdd9239c2927857b")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-plus"  # 使用 qwen-plus 作为兼容模型名

# Lumibot 策略生成系统提示词
SYSTEM_PROMPT = """你是一个专业的量化交易策略助手，专门帮助用户用 Python 和 lumibot 框架创建交易策略。

## 你的能力
- 理解用户的自然语言策略描述
- 生成完整、可运行的 lumibot Python 策略类代码
- 解释策略逻辑和风险
- 根据用户反馈调整策略参数

## Lumibot 框架核心知识

### 策略类基本结构
```python
from lumibot.strategies.strategy import Strategy

class MyStrategy(Strategy):
    parameters = {
        "symbol": "SPY",      # 交易标的
        "quantity": 10,        # 数量
    }
    
    def initialize(self):
        self.sleeptime = "1D"  # 执行频率: "1D"=每天, "1H"=每小时, "30M"=30分钟
    
    def on_trading_iteration(self):
        # 核心交易逻辑（每个 sleeptime 执行一次）
        pass
```

### 常用 API 方法
- `self.get_last_price(symbol)` — 获取最新价格
- `self.get_historical_prices(symbol, length, timestep="day")` — 获取历史 K 线
- `self.get_portfolio_value()` — 获取当前组合总价值
- `self.get_cash()` — 获取可用现金
- `self.get_position(symbol)` — 获取某标的持仓
- `self.get_positions()` — 获取所有持仓
- `self.create_order(symbol, quantity, "buy"/"sell")` — 创建订单
- `self.submit_order(order)` — 提交订单
- `self.sell_all()` — 卖出全部持仓
- `self.log_message(msg)` — 记录日志

### 历史数据使用示例
```python
bars = self.get_historical_prices("SPY", 20, timestep="day")
if bars is not None:
    df = bars.df
    close_prices = df["close"]
    ma20 = close_prices.mean()  # 20日均线
```

### 常见策略模式

**买入持有**:
```python
def on_trading_iteration(self):
    if not self.get_position("SPY"):
        price = self.get_last_price("SPY")
        qty = int(self.get_portfolio_value() / price)
        self.submit_order(self.create_order("SPY", qty, "buy"))
```

**均线交叉**:
```python
def on_trading_iteration(self):
    bars = self.get_historical_prices("SPY", 50, timestep="day")
    if bars is None:
        return
    df = bars.df
    ma_short = df["close"][-10:].mean()
    ma_long = df["close"][-50:].mean()
    position = self.get_position("SPY")
    if ma_short > ma_long and not position:
        price = self.get_last_price("SPY")
        qty = int(self.get_portfolio_value() / price)
        self.submit_order(self.create_order("SPY", qty, "buy"))
    elif ma_short < ma_long and position:
        self.sell_all()
```

**动量策略**:
- 计算多个标的的历史收益率
- 买入近期涨幅最大的标的

## 代码规范
1. 策略类名必须清晰（如 `BuyAndHold`, `MomentumStrategy`, `MACrossover`）
2. `parameters` 字典包含所有可调参数
3. 必须实现 `initialize()` 和 `on_trading_iteration()` 方法
4. 代码必须用中文注释解释关键逻辑
5. 不要包含 `if __name__ == "__main__":` 部分（由系统处理回测）
6. 禁止使用 `os`, `subprocess`, `sys`, `open` 等系统操作

## 回复格式
当用户描述策略时，请按以下格式回复：

1. **策略分析**：简要分析用户的策略思路（2-3句话）
2. **策略代码**：用```python 代码块包裹完整的策略类
3. **参数说明**：列出关键参数及其含义
4. **风险提示**：简短的风险提示（1-2句话）

请始终用中文回复。
"""


class AIEngine:
    """阿里云百炼 AI 对话引擎"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
        )
        self.model = MODEL_NAME
    
    def chat(self, user_message: str, history: list = None) -> dict:
        """
        与 AI 进行对话，返回策略分析和代码
        
        Args:
            user_message: 用户输入的策略描述
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
        
        Returns:
            dict: {"reply": str, "code": str | None, "error": str | None}
        """
        if history is None:
            history = []
        
        # 构建消息列表
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=3000,
                stream=False,
            )
            
            reply = response.choices[0].message.content
            
            # 提取代码块
            code = self._extract_code(reply)
            
            return {
                "reply": reply,
                "code": code,
                "error": None,
            }
        
        except Exception as e:
            return {
                "reply": f"AI 服务暂时不可用，请稍后重试。错误信息：{str(e)}",
                "code": None,
                "error": str(e),
            }
    
    def _extract_code(self, text: str) -> str | None:
        """从 AI 回复中提取 Python 代码块"""
        import re
        
        # 提取 ```python ... ``` 代码块
        pattern = r"```python\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        
        if matches:
            # 取最长的一个代码块（通常是完整策略代码）
            return max(matches, key=len).strip()
        
        return None
    
    def generate_strategy_code(self, description: str) -> dict:
        """
        直接生成策略代码（单次调用，不需要历史）
        
        Args:
            description: 策略描述
        
        Returns:
            dict: {"reply": str, "code": str | None, "error": str | None}
        """
        prompt = f"请根据以下策略描述，生成完整的 lumibot 策略代码：\n\n{description}"
        return self.chat(prompt)
