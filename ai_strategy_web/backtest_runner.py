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
    ) -> str:
        """
        提交回测任务，返回 task_id
        
        Args:
            strategy_code:   策略 Python 代码（含 import）
            start_date:      "2022-01-01"
            end_date:        "2024-01-01"
            budget:          初始资金（美元）
            benchmark:       基准标的代码
            strategy_params: 覆盖策略 parameters 字典（可选）
        """
        task_id = str(uuid.uuid4())[:8]
        task = BacktestTask(task_id)
        
        with self._lock:
            self._tasks[task_id] = task
        
        thread = threading.Thread(
            target=self._run,
            args=(task, strategy_code, start_date, end_date, budget, benchmark, strategy_params),
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
            
            # 4. 执行回测（使用 Yahoo 免费数据源）
            task.progress = 30
            task.progress_msg = "正在执行回测（Yahoo Finance 数据）..."
            
            from lumibot.backtesting import YahooDataBacktesting
            
            results, strategy = strategy_class.run_backtest(
                datasource_class=YahooDataBacktesting,
                backtesting_start=bt_start,
                backtesting_end=bt_end,
                budget=budget,
                benchmark_asset=benchmark,
                show_plot=False,
                show_tearsheet=False,
                save_tearsheet=False,
                show_indicators=False,
                save_logfile=False,
                analyze_backtest=True,
                parameters=run_params if run_params else None,
                quiet_logs=True,
            )
            
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
            # 尝试从 strategy._stats 获取时间序列
            stats = getattr(strategy, "_stats", None) or getattr(strategy, "stats", None)
            
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
            
            ax.plot(df.index, df["portfolio_value"], color="#00d4ff", linewidth=2, label="策略净值")
            ax.fill_between(df.index, df["portfolio_value"], alpha=0.1, color="#00d4ff")
            
            ax.set_xlabel("日期", color="#aaaacc")
            ax.set_ylabel("资产价值 ($)", color="#aaaacc")
            ax.set_title("策略资产价值曲线", color="#ffffff", fontsize=14, fontweight="bold")
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
        
        except Exception:
            return self._generate_placeholder_chart()
    
    def _generate_placeholder_chart(self) -> str:
        """生成占位图（无数据时）"""
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor("#1a1a2e")
        ax.set_facecolor("#16213e")
        ax.text(0.5, 0.5, "图表数据暂不可用", transform=ax.transAxes,
                ha="center", va="center", color="#aaaacc", fontsize=16)
        ax.set_axis_off()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")


# 全局单例
_runner_instance = None

def get_runner() -> BacktestRunner:
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = BacktestRunner()
    return _runner_instance
