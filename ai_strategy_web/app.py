"""
Flask 主服务
提供 REST API 接口，连接 AI 引擎、策略生成器和回测执行器
"""

import os
import sys
import json
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS

# 将当前目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 将 lumibot 根目录加入路径（上一级目录）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine import AIEngine
from strategy_generator import StrategyGenerator, EXAMPLE_STRATEGIES
from backtest_runner import get_runner

app = Flask(__name__)
CORS(app)

# 全局实例
ai_engine = AIEngine()
strategy_gen = StrategyGenerator()
backtest_runner = get_runner()


# ════════════════════════════════════════════════════════════
#   页面路由
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """主页面"""
    return render_template("index.html")


# ════════════════════════════════════════════════════════════
#   AI 对话接口
# ════════════════════════════════════════════════════════════

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    与 AI 对话，返回策略分析和代码
    
    请求体:
        {
            "message": "用户输入的策略描述",
            "history": [{"role": "user/assistant", "content": "..."}],
            "ai_config": {          // 可选的 AI 参数配置
                "temperature": 0.7,
                "model": "qwen-plus"
            }
        }
    
    返回:
        {
            "reply": "AI 回复文本",
            "code": "提取的 Python 代码（或 null）",
            "strategy_info": {
                "class_name": "...",
                "parameters": {...},
                "description": "..."
            },
            "error": null
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400
    
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "消息不能为空"}), 400
    
    history = data.get("history", [])
    ai_config = data.get("ai_config", {})
    
    # 动态调整 AI 配置（温度、模型等）
    if "temperature" in ai_config:
        ai_engine.client.timeout = 60  # 确保超时合理
    
    # 调用 AI 对话
    result = ai_engine.chat(user_message, history, ai_config=ai_config)
    
    # 如果生成了代码，解析策略信息
    strategy_info = None
    if result.get("code"):
        try:
            full_code = strategy_gen.prepare_full_code(result["code"])
            strategy_info = strategy_gen.extract_strategy_info(full_code)
        except Exception as e:
            strategy_info = {"error": str(e)}
    
    return jsonify({
        "reply": result.get("reply", ""),
        "code": result.get("code"),
        "strategy_info": strategy_info,
        "error": result.get("error"),
    })


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    直接根据描述生成策略代码（不需要对话历史）
    
    请求体:
        {"description": "策略描述文本"}
    """
    data = request.get_json()
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"error": "策略描述不能为空"}), 400
    
    result = ai_engine.generate_strategy_code(description)
    
    strategy_info = None
    if result.get("code"):
        try:
            full_code = strategy_gen.prepare_full_code(result["code"])
            strategy_info = strategy_gen.extract_strategy_info(full_code)
        except Exception as e:
            strategy_info = {"error": str(e)}
    
    return jsonify({
        "reply": result.get("reply", ""),
        "code": result.get("code"),
        "strategy_info": strategy_info,
        "error": result.get("error"),
    })


# ════════════════════════════════════════════════════════════
#   策略验证接口
# ════════════════════════════════════════════════════════════

@app.route("/api/validate", methods=["POST"])
def api_validate():
    """
    验证策略代码是否符合 lumibot 规范
    
    请求体:
        {"code": "Python 策略代码"}
    """
    data = request.get_json()
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "代码不能为空"}), 400
    
    full_code = strategy_gen.prepare_full_code(code)
    is_valid, error_msg = strategy_gen.validate_code(full_code)
    strategy_info = strategy_gen.extract_strategy_info(full_code) if is_valid else None
    
    return jsonify({
        "is_valid": is_valid,
        "error": error_msg if not is_valid else None,
        "strategy_info": strategy_info,
    })


# ════════════════════════════════════════════════════════════
#   回测接口
# ════════════════════════════════════════════════════════════

@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    """
    启动回测任务
    
    请求体:
        {
            "code": "策略 Python 代码",
            "start_date": "2022-01-01",
            "end_date": "2024-01-01",
            "budget": 100000,
            "benchmark": "SPY",
            "strategy_params": {"buy_symbol": "QQQ"}  // 可选，覆盖策略参数
        }
    
    返回:
        {"task_id": "abc12345"}
    """
    data = request.get_json()
    
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "策略代码不能为空"}), 400
    
    start_date = data.get("start_date", "2022-01-01")
    end_date   = data.get("end_date",   "2024-01-01")
    budget     = float(data.get("budget", 100_000))
    benchmark  = data.get("benchmark", "SPY")
    strategy_params = data.get("strategy_params", {})
    data_source = data.get("data_source", "yahoo")
    data_source_config = data.get("data_source_config", {})
    
    task_id = backtest_runner.submit(
        strategy_code=code,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        benchmark=benchmark,
        strategy_params=strategy_params or {},
        data_source=data_source,
        data_source_config=data_source_config or {},
    )
    
    return jsonify({"task_id": task_id})


@app.route("/api/backtest/status/<task_id>")
def api_backtest_status(task_id: str):
    """查询回测任务状态"""
    status = backtest_runner.get_status(task_id)
    return jsonify(status)


@app.route("/api/backtest/result/<task_id>")
def api_backtest_result(task_id: str):
    """获取回测结果（含图表 base64）"""
    result = backtest_runner.get_result(task_id)
    return jsonify(result)

@app.route("/api/backtest/tearsheet/<task_id>")
def api_backtest_tearsheet(task_id: str):
    """展示由 Lumibot Quantstats 生成的高级详细 HTML 报告"""
    task = backtest_runner.get_task(task_id)
    if not task:
        return "Task not found", 404
    if not task.tearsheet_path or not os.path.exists(task.tearsheet_path):
        return "Tearsheet not generated for this task", 404
        
    try:
        with open(task.tearsheet_path, "r", encoding="utf-8") as f:
            html = f.read()
        return Response(html, mimetype="text/html")
    except Exception as e:
        return f"Error loading tearsheet: {str(e)}", 500


# ════════════════════════════════════════════════════════════
#   示例策略接口
# ════════════════════════════════════════════════════════════

@app.route("/api/examples")
def api_examples():
    """获取预设示例策略列表"""
    # 只返回不含完整代码的简要信息
    examples = [
        {
            "id": e["id"],
            "name": e["name"],
            "description": e["description"],
            "prompt": e["prompt"],
            "has_code": e["code"] is not None,
            "code": e.get("code"),
        }
        for e in EXAMPLE_STRATEGIES
    ]
    return jsonify(examples)


# ════════════════════════════════════════════════════════════
#   配置接口
# ════════════════════════════════════════════════════════════

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """获取当前服务配置（前端可读取默认值）"""
    return jsonify({
        "ai": {
            "model": ai_engine.model,
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "available_models": [
                {"id": "qwen-plus",      "name": "Qwen Plus (推荐)"},
            ],
        },
        "backtest": {
            "default_start": "2022-01-01",
            "default_end":   "2024-12-31",
            "default_budget": 100_000,
            "default_benchmark": "SPY",
            "benchmarks": ["SPY", "QQQ", "IWM", "BTC-USD", "GLD"],
            "default_data_source": "yahoo",
            "available_data_sources": [
                {
                    "id": "yahoo",
                    "name": "Yahoo Finance（免费）",
                    "description": "无需注册，开箱即用，数据覆盖全球主要市场，历史日线可追溯15年以上，适合入门和快速验证策略。",
                    "features": ["✅ 完全免费", "📅 日线数据", "🌍 全球市场", "🔓 无需注册"],
                    "requires_key": False,
                },
                {
                    "id": "alpaca",
                    "name": "Alpaca Markets",
                    "description": "免费Paper Account，美股/加密货币数据，支持日线+分钟线，数据质量优于Yahoo，适合中高频策略验证。",
                    "features": ["✅ 免费注册", "⏱️ 分钟级数据", "📈 更高数据质量", "🔑 需要 API Key"],
                    "requires_key": True,
                    "key_fields": [
                        {"id": "API_KEY",    "label": "API Key",    "type": "text"},
                        {"id": "API_SECRET", "label": "API Secret", "type": "password"},
                    ],
                    "signup_url": "https://alpaca.markets",
                },
                {
                    "id": "polygon",
                    "name": "Polygon.io",
                    "description": "专业数据供应商，支持股票、期权、外汇，免费计划15分钟延迟但历史日线完整齐全，数据质量最佳。",
                    "features": ["✅ 免费注册", "📊 支持期权数据", "⭐ 数据质量最佳", "🔑 需要 API Key"],
                    "requires_key": True,
                    "key_fields": [
                        {"id": "API_KEY", "label": "API Key", "type": "text"},
                    ],
                    "signup_url": "https://polygon.io",
                },
            ],
        },
        "version": "1.0.0",
    })


@app.route("/api/config/model", methods=["POST"])
def api_set_model():
    """动态切换 AI 模型"""
    data = request.get_json()
    new_model = data.get("model", "").strip()
    if not new_model:
        return jsonify({"error": "模型名称不能为空"}), 400
    
    ai_engine.model = new_model
    return jsonify({"success": True, "model": new_model})


# ════════════════════════════════════════════════════════════
#   启动
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    debug = os.getenv("DEBUG", "true").lower() == "true"
    print(f"\n🚀 AI 策略生成器已启动！")
    print(f"   访问地址：http://localhost:{port}")
    print(f"   AI 模型：{ai_engine.model}")
    print(f"   调试模式：{debug}\n")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
