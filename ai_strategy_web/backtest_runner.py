"""
异步回测执行器
使用线程池执行 lumibot 回测，支持进度查询和结果获取
"""

import threading
import uuid
import traceback
import io
import base64
import logging
import datetime
from typing import Optional
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 配置 matplotlib 支持中文
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.max_open_warning'] = 0

# 抑制回测期间的 matplotlib 图形显示
logging.getLogger("matplotlib").setLevel(logging.WARNING)


class BacktestTask:
    """单个回测任务"""
    
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.status = self.STATUS_PENDING
        self.progress = 0          # 0~100
        self.progress_msg = "等待中..."
        self.result = None         # 回测成功后的指标字典
        self.chart_b64 = None      # 资产曲线图的 base64 PNG
        self.tearsheet_path = None # html 报告保存路径
        self.error = None          # 错误信息
        self.created_at = datetime.datetime.now()


class BacktestRunner:
    """回测任务管理器（单例）"""
    
    def __init__(self):
        self._tasks: dict[str, BacktestTask] = {}
        self._lock = threading.Lock()
    
    # ── 公共接口 ────────────────────────────────────────────────────────────
    
    def submit(
        self,
        strategy_code: str,
        start_date: str,
        end_date: str,
        budget: float = 100_000,
        benchmark: str = "SPY",
        strategy_params: dict = None,
        data_source: str = "yahoo",
        data_source_config: dict = None,
    ) -> str:
        """
        提交回测任务，返回 task_id
        
        Args:
            strategy_code:     策略 Python 代码（含 import）
            start_date:        "2022-01-01"
            end_date:          "2024-01-01"
            budget:            初始资金（美元）
            benchmark:         基准标的代码
            strategy_params:   覆盖策略 parameters 字典（可选）
            data_source:       数据源标识，支持 "yahoo" / "alpaca"（默认 yahoo）
            data_source_config: 数据源配置字典（alpaca 需传入 API_KEY / API_SECRET）
        """
        task_id = str(uuid.uuid4())[:8]
        task = BacktestTask(task_id)
        
        with self._lock:
            self._tasks[task_id] = task
        
        thread = threading.Thread(
            target=self._run,
            args=(task, strategy_code, start_date, end_date, budget, benchmark,
                  strategy_params, data_source, data_source_config),
            daemon=True,
        )
        thread.start()
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[BacktestTask]:
        """获取任务对象"""
        return self._tasks.get(task_id)
    
    def get_status(self, task_id: str) -> dict:
        """获取任务状态"""
        task = self.get_task(task_id)
        if task is None:
            return {"error": "任务不存在"}
        return {
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "progress_msg": task.progress_msg,
            "error": task.error,
        }
    
    def get_result(self, task_id: str) -> dict:
        """获取回测结果（含图表）"""
        task = self.get_task(task_id)
        if task is None:
            return {"error": "任务不存在"}
        if task.status != BacktestTask.STATUS_DONE:
            return {"error": f"回测尚未完成，当前状态: {task.status}"}
        return {
            "task_id": task.task_id,
            "result": task.result,
            "chart_b64": task.chart_b64,
            "has_tearsheet": bool(task.tearsheet_path)
        }
    
    # ── 内部实现 ────────────────────────────────────────────────────────────
    
    def _run(
        self,
        task: BacktestTask,
        strategy_code: str,
        start_date: str,
        end_date: str,
        budget: float,
        benchmark: str,
        strategy_params: dict,
        data_source: str = "yahoo",
        data_source_config: dict = None,
    ):
        """在后台线程中执行回测"""
        task.status = BacktestTask.STATUS_RUNNING
        task.progress = 5
        task.progress_msg = "正在加载策略代码..."
        
        try:
            # 1. 动态加载策略类
            from strategy_generator import StrategyGenerator
            gen = StrategyGenerator()
            strategy_class = gen.get_strategy_class(strategy_code)
            
            task.progress = 20
            task.progress_msg = "正在初始化回测环境..."
            
            # 2. 解析日期
            import pytz
            tz = pytz.timezone("America/New_York")
            fmt = "%Y-%m-%d"
            bt_start = tz.localize(datetime.datetime.strptime(start_date, fmt))
            bt_end   = tz.localize(datetime.datetime.strptime(end_date,   fmt))
            
            # 3. 合并策略参数（用户在前端覆盖的）
            run_params = {}
            if strategy_params:
                run_params.update(strategy_params)
            
            # 4. 根据数据源选择对应的回测类
            data_source = (data_source or "yahoo").lower()
            datasource_class, extra_kwargs = self._resolve_datasource(
                data_source, data_source_config or {}
            )
            
            source_label = {
                "yahoo": "Yahoo Finance",
                "alpaca": "Alpaca Markets",
                "polygon": "Polygon.io",
            }.get(data_source, data_source)
            task.progress = 30
            task.progress_msg = f"正在执行回测（{source_label} 数据）..."
            
            results, strategy = strategy_class.run_backtest(
                datasource_class=datasource_class,
                backtesting_start=bt_start,
                backtesting_end=bt_end,
                budget=budget,
                benchmark_asset=benchmark,
                show_plot=False,
                show_tearsheet=False,
                save_tearsheet=True,
                show_indicators=False,
                save_logfile=False,
                analyze_backtest=True,
                parameters=run_params if run_params else None,
                quiet_logs=True,
                **extra_kwargs,
            )
            
            # 由于开启了 save_tearsheet=True，会在 logs 留下 html
            # 这里获取最新的那个 html 作为此任务的详细报告：
            import glob
            import os
            try:
                tearsheets = glob.glob(os.path.join("logs", "*_tearsheet.html"))
                if tearsheets:
                    latest_html = max(tearsheets, key=os.path.getmtime)
                    task.tearsheet_path = latest_html
            except Exception as e:
                logging.error(f"寻找 tearsheet html 失败: {e}")
            
            self._cleanup_logs()
            
            task.progress = 85
            task.progress_msg = "正在生成分析图表..."
            
            # 5. 解析结果指标
            task.result = self._parse_results(results)
            
            # 6. 生成资产曲线图
            task.chart_b64 = self._generate_chart(strategy, benchmark)
            
            task.progress = 100
            task.progress_msg = "回测完成！"
            task.status = BacktestTask.STATUS_DONE
        
        except Exception as e:
            task.status = BacktestTask.STATUS_ERROR
            task.error = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            task.progress_msg = "回测失败"
    
    def _parse_results(self, results) -> dict:
        """解析回测结果为前端友好的字典"""
        if results is None:
            return {}
        
        def safe_float(v, default=0.0):
            try:
                val = float(v)
                if pd.isna(val) or val != val:
                    return default
                return round(val, 4)
            except Exception:
                return default
        
        def pct(v):
            """转换为百分比字符串"""
            f = safe_float(v)
            return f"{f * 100:.2f}%"
        
        metrics = {}
        
        # 将 results（可能是 dict 或 StrategyAnalysis 对象）转为 dict
        if hasattr(results, "__dict__"):
            r = results.__dict__
        elif isinstance(results, dict):
            r = results
        else:
            r = {}
        
        metrics["total_return"]           = pct(r.get("total_return",           r.get("cagr", 0)))
        metrics["cagr"]                   = pct(r.get("cagr",                   0))
        metrics["sharpe_ratio"]           = safe_float(r.get("sharpe",          r.get("sharpe_ratio", 0)))
        metrics["max_drawdown"]           = pct(r.get("max_drawdown",           0))
        metrics["volatility"]             = pct(r.get("annual_volatility",      r.get("volatility", 0)))
        metrics["win_rate"]               = pct(r.get("win_rate",               0))
        metrics["profit_factor"]          = safe_float(r.get("profit_factor",   0))
        metrics["total_trades"]           = int(r.get("total_trades",           0))
        metrics["benchmark_return"]       = pct(r.get("benchmark_return",       0))
        metrics["alpha"]                  = safe_float(r.get("alpha",           0))
        metrics["beta"]                   = safe_float(r.get("beta",            0))
        metrics["calmar_ratio"]           = safe_float(r.get("calmar",          0))
        
        return metrics
    
    def _generate_chart(self, strategy, benchmark: str) -> str:
        """生成资产价值曲线的 base64 PNG 图"""
        try:
            # 安全地获取 stats 时间序列
            stats = getattr(strategy, "_stats", None)
            if stats is None:
                stats = getattr(strategy, "stats", None)
            
            if stats is None or not hasattr(stats, "__len__") or len(stats) == 0:
                return self._generate_placeholder_chart()
            
            df = None
            if isinstance(stats, pd.DataFrame):
                df = stats
            elif hasattr(stats, "portfolio_value"):
                df = pd.DataFrame({"portfolio_value": stats.portfolio_value})
            
            if df is None or "portfolio_value" not in df.columns:
                return self._generate_placeholder_chart()
            
            # 绘图
            fig, ax = plt.subplots(figsize=(10, 5))
            fig.patch.set_facecolor("#1a1a2e")
            ax.set_facecolor("#16213e")
            
            ax.plot(df.index, df["portfolio_value"], color="#00d4ff", linewidth=2, label="Strategy Value")
            ax.fill_between(df.index, df["portfolio_value"], alpha=0.1, color="#00d4ff")
            
            ax.set_xlabel("Date", color="#aaaacc")
            ax.set_ylabel("Portfolio Value ($)", color="#aaaacc")
            ax.set_title("Strategy Portfolio Value Curve", color="#ffffff", fontsize=14, fontweight="bold")
            ax.tick_params(colors="#aaaacc")
            ax.spines["bottom"].set_color("#333355")
            ax.spines["left"].set_color("#333355")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.legend(facecolor="#1a1a2e", edgecolor="#333355", labelcolor="#aaaacc")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            plt.xticks(rotation=30)
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("utf-8")
        
        except Exception as e:
            import traceback
            logging.error(f"图表生成失败: {e}\n{traceback.format_exc()}")
            return self._generate_placeholder_chart()
    
    def _generate_placeholder_chart(self) -> str:
        """生成占位图（无数据时）"""
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#16213e")
        ax.text(0.5, 0.5, "No Chart Data Available", transform=ax.transAxes,
                ha="center", va="center", color="#aaaacc", fontsize=16)
        ax.set_axis_off()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    def _resolve_datasource(self, data_source: str, config: dict) -> tuple:
        """
        根据数据源标识返回 (datasource_class, extra_kwargs)

        支持的数据源：
            "yahoo"  - YahooDataBacktesting，无需 API Key
            "alpaca" - AlpacaBacktesting，需 API_KEY + API_SECRET
        """
        if data_source == "alpaca":
            from lumibot.backtesting import AlpacaBacktesting
            api_key = config.get("API_KEY", "")
            api_secret = config.get("API_SECRET", "")
            if not api_key or not api_secret:
                raise ValueError(
                    "使用 Alpaca 数据源需要提供 API_KEY 和 API_SECRET。\n"
                    "请在前端设置面板中填写 Alpaca API 凭证。\n"
                    "免费注册地址：https://alpaca.markets"
                )
            alpaca_config = {
                "API_KEY": api_key,
                "API_SECRET": api_secret,
                "PAPER": True,  # 回测须使用 Paper 账户
            }
            return AlpacaBacktesting, {"config": alpaca_config}

        elif data_source == "polygon":
            from lumibot.backtesting import PolygonDataBacktesting
            import os
            api_key = config.get("API_KEY", "")
            if not api_key:
                raise ValueError(
                    "使用 Polygon.io 数据源需要提供 API_KEY。\n"
                    "请在前端设置面板中填写 Polygon API Key。\n"
                    "免费注册地址：https://polygon.io"
                )
            # Polygon 需要通过 run_backtest 的 polygon_api_key 参数传入 Key
            os.environ["POLYGON_API_KEY"] = api_key  # 双保险
            return PolygonDataBacktesting, {"polygon_api_key": api_key}

        else:
            # 默认 Yahoo Finance（免费，无需 Key）
            from lumibot.backtesting import YahooDataBacktesting
            return YahooDataBacktesting, {}

    def _cleanup_logs(self, max_files=10):
        """定期清理旧的 logs 文件，防止累积过多"""
        import os
        import glob
        import shutil
        try:
            if not os.path.exists("logs"):
                return
            # 获取所有的 tearsheet 文件，倒序（最新的在前）
            tearsheets = sorted(glob.glob(os.path.join("logs", "*_tearsheet.html")), key=os.path.getmtime, reverse=True)
            if len(tearsheets) > max_files:
                for old_html in tearsheets[max_files:]:
                    prefix = old_html.replace("_tearsheet.html", "")
                    # 删除所有同前缀的 csv, parquet 等
                    for f in glob.glob(f"{prefix}*"):
                        try:
                            os.remove(f)
                        except Exception:
                            pass
        except Exception as e:
            logging.error(f"清理 logs 失败: {e}")


# 全局单例
_runner_instance = None

def get_runner() -> BacktestRunner:
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = BacktestRunner()
    return _runner_instance
