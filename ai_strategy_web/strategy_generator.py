"""
策略代码生成器
负责验证、解析和动态加载 AI 生成的 lumibot 策略代码
"""

import re
import ast
import sys
import importlib
import importlib.util
import tempfile
import os
from typing import Optional


# 禁止使用的危险模块和函数
FORBIDDEN_IMPORTS = {
    "os", "subprocess", "sys", "shutil", "pathlib", "glob",
    "socket", "http", "urllib", "requests", "aiohttp",
    "pickle", "marshal", "shelve",
    "__import__", "exec", "eval", "compile", "open",
}

FORBIDDEN_PATTERNS = [
    r"\bos\.system\b",
    r"\bsubprocess\.",
    r"\bopen\s*\(",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bcompile\s*\(",
]


class StrategyValidator:
    """策略代码安全验证器"""
    
    def validate(self, code: str) -> tuple[bool, str]:
        """
        验证策略代码是否安全
        
        Returns:
            (is_valid, error_message)
        """
        # 检查危险模式
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, code):
                return False, f"策略代码包含不允许的操作: {pattern}"
        
        # 尝试解析 AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"代码语法错误: {str(e)}"
        
        # 检查危险导入
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_root = alias.name.split(".")[0]
                        if module_root in FORBIDDEN_IMPORTS:
                            return False, f"不允许导入模块: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_root = node.module.split(".")[0]
                        if module_root in FORBIDDEN_IMPORTS:
                            return False, f"不允许导入模块: {node.module}"
        
        # 检查是否包含 Strategy 子类
        has_strategy_class = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if base_name == "Strategy":
                        has_strategy_class = True
                        break
        
        if not has_strategy_class:
            return False, "代码中未找到继承自 Strategy 的策略类"
        
        return True, ""


class StrategyGenerator:
    """策略代码管理器"""
    
    def __init__(self):
        self.validator = StrategyValidator()
    
    def validate_code(self, code: str) -> tuple[bool, str]:
        """验证策略代码"""
        return self.validator.validate(code)
    
    def extract_strategy_info(self, code: str) -> dict:
        """
        从代码中解析策略信息
        
        Returns:
            dict: {
                "class_name": str,       # 策略类名
                "parameters": dict,      # 参数字典
                "has_initialize": bool,  # 是否有 initialize 方法
                "has_iteration": bool,   # 是否有 on_trading_iteration 方法
                "description": str,      # 代码文档字符串
            }
        """
        info = {
            "class_name": "UnknownStrategy",
            "parameters": {},
            "has_initialize": False,
            "has_iteration": False,
            "description": "",
        }
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return info
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # 检查是否继承自 Strategy
                is_strategy = False
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "Strategy":
                        is_strategy = True
                    elif isinstance(base, ast.Attribute) and base.attr == "Strategy":
                        is_strategy = True
                
                if not is_strategy:
                    continue
                
                info["class_name"] = node.name
                
                # 获取类文档字符串
                if (node.body and
                        isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant)):
                    info["description"] = node.body[0].value.value
                
                # 遍历类方法和属性
                for item in node.body:
                    # 提取 parameters 字典
                    if (isinstance(item, ast.Assign) and
                            len(item.targets) == 1 and
                            isinstance(item.targets[0], ast.Name) and
                            item.targets[0].id == "parameters"):
                        try:
                            info["parameters"] = ast.literal_eval(item.value)
                        except (ValueError, TypeError):
                            pass
                    
                    # 检查方法
                    if isinstance(item, ast.FunctionDef):
                        if item.name == "initialize":
                            info["has_initialize"] = True
                        elif item.name == "on_trading_iteration":
                            info["has_iteration"] = True
                
                break  # 找到第一个策略类就停止
        
        return info
    
    def prepare_full_code(self, user_code: str) -> str:
        """
        为用户代码添加必要的 import 语句
        
        Args:
            user_code: 用户的策略代码（可能缺少 import）
        
        Returns:
            完整可执行的代码
        """
        # 检查是否已有必要的 import
        has_strategy_import = "from lumibot.strategies" in user_code or "from lumibot.strategies.strategy import Strategy" in user_code
        
        header = ""
        if not has_strategy_import:
            header = "from lumibot.strategies.strategy import Strategy\nimport datetime\nimport pandas as pd\nimport numpy as np\n\n"
        
        return header + user_code
    
    def get_strategy_class(self, code: str):
        """
        动态加载策略类
        
        Args:
            code: 完整的策略 Python 代码
        
        Returns:
            策略类对象 或 None
        """
        # 准备完整代码
        full_code = self.prepare_full_code(code)
        
        # 验证代码安全性
        is_valid, error = self.validate_code(full_code)
        if not is_valid:
            raise ValueError(f"代码验证失败: {error}")
        
        # 获取策略信息
        info = self.extract_strategy_info(full_code)
        class_name = info["class_name"]
        
        # 写入临时文件并动态导入
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            prefix='lumibot_strategy_',
            encoding='utf-8'
        ) as f:
            f.write(full_code)
            temp_path = f.name
        
        try:
            spec = importlib.util.spec_from_file_location("dynamic_strategy", temp_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            strategy_class = getattr(module, class_name, None)
            if strategy_class is None:
                raise ValueError(f"在代码中未找到策略类: {class_name}")
            
            return strategy_class
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except Exception:
                pass


# 预设示例策略
EXAMPLE_STRATEGIES = [
    {
        "id": "buy_and_hold",
        "name": "买入持有 SPY",
        "description": "买入并长期持有标普500指数ETF（SPY），适合长期投资者",
        "prompt": "帮我创建一个买入并持有SPY的策略，一次性买入全仓，长期持有不动",
        "code": """from lumibot.strategies.strategy import Strategy

class BuyAndHold(Strategy):
    \"\"\"买入并持有策略 - 一次性买入目标资产，长期持有\"\"\"
    
    parameters = {
        "buy_symbol": "SPY",  # 要购买的ETF代码
    }
    
    def initialize(self):
        # 每天检查一次仓位
        self.sleeptime = "1D"
    
    def on_trading_iteration(self):
        buy_symbol = self.parameters["buy_symbol"]
        current_price = self.get_last_price(buy_symbol)
        self.log_message(f"{buy_symbol} 当前价格: {current_price}")
        
        # 如果没有持仓，则买入全仓
        all_positions = self.get_positions()
        if len(all_positions) == 0:
            quantity = int(self.get_portfolio_value() / current_price)
            if quantity > 0:
                order = self.create_order(buy_symbol, quantity, "buy")
                self.submit_order(order)
                self.log_message(f"买入 {quantity} 股 {buy_symbol}")
"""
    },
    {
        "id": "momentum",
        "name": "动量轮动策略",
        "description": "在多个ETF中选择近期表现最好的持有，定期轮换",
        "prompt": "帮我创建一个动量策略，在SPY、QQQ、IWM三个ETF中选择过去20天涨幅最大的持有，每周重新评估",
        "code": None  # 由 AI 生成
    },
    {
        "id": "ma_crossover",
        "name": "均线交叉策略",
        "description": "短期均线上穿长期均线时买入，下穿时卖出",
        "prompt": "帮我创建一个SPY的双均线策略：10日均线上穿50日均线时买入，下穿时清仓卖出",
        "code": None  # 由 AI 生成
    },
    {
        "id": "rebalance_6040",
        "name": "60/40 经典组合",
        "description": "60% 股票 + 40% 债券，定期再平衡",
        "prompt": "帮我创建一个经典的60/40组合策略：60%买SPY（股票），40%买TLT（债券），每月重新平衡一次",
        "code": None  # 由 AI 生成
    },
]
