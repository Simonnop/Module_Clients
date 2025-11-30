"""
配置文件
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（从当前目录或上级目录）
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # 尝试从上级目录加载
    parent_env_path = Path(__file__).parent.parent / '.env'
    if parent_env_path.exists():
        load_dotenv(parent_env_path)

# 服务器配置（从环境变量读取）
SERVER_IP = os.getenv('SERVER_IP')
SERVER_PORT = os.getenv('SERVER_PORT')

# WebSocket配置
HEARTBEAT_INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL', '10'))  # 心跳间隔（秒），默认10秒

# 验证必需配置
if not SERVER_IP:
    raise ValueError("环境变量 SERVER_IP 未设置，请在 .env 文件中配置")
if not SERVER_PORT:
    raise ValueError("环境变量 SERVER_PORT 未设置，请在 .env 文件中配置")
SERVER_PORT = int(SERVER_PORT)

CONFIG = {
    # 模块信息
    "name": "股票RSI监控模块",
    "description": "监控股票RSI指标，当RSI指标超过阈值时发送邮件通知",

    # 输入数据需求
    "input_data": [
        {
            "name": "items",
            "type": "array",
            "description": "RSI 监控列表，包含阈值和通知邮箱，触发一次后当天禁止重复通知",
            "items": {
                "code": "string",
                "name": "string",
                "rsi_high": "number",
                "rsi_low": "number",
                "emails": "array"
            }
        }
    ],
    
    # 输出数据需求
    "output_data": [
        {
            "name": "items",
            "type": "array",
            "description": "每个 item 返回 RSI 当前值、价格、告警类型、是否已通知等信息"
        },
        {
            "name": "errors",
            "type": "array",
            "description": "RSI 监控过程中的错误或数据缺失提示"
        }
    ]
}

