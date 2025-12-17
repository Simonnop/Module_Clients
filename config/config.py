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
    "name": "股票双均线监控模块",
    "description": "监控股票双均线金叉/死叉，触发时发送邮件通知并记录信号",

    # 输入数据需求
    "input_data": [],
    
    # 输出数据需求
    "output_data": []
}

