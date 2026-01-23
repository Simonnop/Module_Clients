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

# LLM API 配置
LLM_API_URL = os.getenv('LLM_API_URL', 'http://127.0.0.1:10101/llm/ask_with_files')  # LLM API 地址

# MongoDB 配置
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:Glgl1234567@127.0.0.1:27017/?authSource=admin')  # MongoDB 连接 URI
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'finance_data')  # MongoDB 数据库名称

# 验证必需配置
if not SERVER_IP:
    raise ValueError("环境变量 SERVER_IP 未设置，请在 .env 文件中配置")
if not SERVER_PORT:
    raise ValueError("环境变量 SERVER_PORT 未设置，请在 .env 文件中配置")
SERVER_PORT = int(SERVER_PORT)

CONFIG = {
    # 模块信息
    "name": "百度云盘文件处理模块",
    "description": "从百度云盘下载指定文件夹中的PDF文件（包含'鉴茶'的文件），使用LLM API提取文本内容，并将结果保存到MongoDB数据库",
    
    # 输入数据需求
    "input_data": [
    ],
    
    # 输出数据需求
    "output_data": [
    ]
}

