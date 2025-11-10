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

# 天气API配置
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY', 'j5i4gDqHL6nGYwx5wi5kRhXjtf2c5qgFX9fzfk0TOo')
WEATHER_APP_ID = os.getenv('WEATHER_APP_ID', '9e21380c-ff19-4c78-b4ea-19558e93a5d3')
WEATHER_DAYS = int(os.getenv('WEATHER_DAYS', '10'))  # 获取未来天数，默认10天

# MongoDB配置（使用完整的连接字符串）
MONGODB_HOST = os.getenv('MONGODB_HOST')
MONGODB_DB = os.getenv('MONGODB_DB_NAME')
MONGODB_COLLECTION = os.getenv('MONGODB_COLLECTION_NAME')

# 验证必需配置
if not SERVER_IP:
    raise ValueError("环境变量 SERVER_IP 未设置，请在 .env 文件中配置")
if not SERVER_PORT:
    raise ValueError("环境变量 SERVER_PORT 未设置，请在 .env 文件中配置")
SERVER_PORT = int(SERVER_PORT)

# 验证MongoDB配置
if not MONGODB_HOST:
    raise ValueError("环境变量 MONGODB_HOST 未设置，请在 .env 文件中配置")
if not MONGODB_DB:
    raise ValueError("环境变量 MONGODB_DB_NAME 未设置，请在 .env 文件中配置")
if not MONGODB_COLLECTION:
    raise ValueError("环境变量 MONGODB_COLLECTION_NAME 未设置，请在 .env 文件中配置")

CONFIG = {

    # 模块信息
    "name": "msn气象预报爬虫",
    "description": "这是一个使用msn气象预报爬虫模块，用于爬取msn气象预报数据并保存到mongodb数据库",
    
    # 输入数据需求
    "input_data": [
        
    ],
    
    # 输出数据需求
    "output_data": [
        
    ]
}

