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

# MongoDB 配置
MONGODB_HOST = os.getenv('MONGODB_HOST')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'finance_data')
MONGODB_COLLECTION_BILI = os.getenv('MONGODB_COLLECTION_BILI', 'bili_info')
MONGODB_COLLECTION_BYDOC = os.getenv('MONGODB_COLLECTION_BYDOC', 'bydoc_info')

# 筛选的名称列表
FILTER_NAMES_STR = os.getenv('FILTER_NAMES', '擒龙,战国时代,鉴茶,波段哥王安松,龙哥第一买点')
FILTER_NAMES = [name.strip() for name in FILTER_NAMES_STR.split(',') if name.strip()]

# LLM API 配置
LLM_API_URL = os.getenv('LLM_API_URL', 'http://localhost:10101/llm/ask')
LLM_MODEL = os.getenv('LLM_MODEL', 'qwen-plus')
LLM_ENABLE_SEARCH = os.getenv('LLM_ENABLE_SEARCH', 'true').lower() == 'true'

# 邮件发送配置
EMAIL_API_URL = os.getenv('EMAIL_API_URL', 'http://localhost:10101/send')
EMAIL_TO_STR = os.getenv('EMAIL_TO', '')
# 解析邮箱列表（支持逗号分隔的多个邮箱）
EMAIL_TO = [email.strip() for email in EMAIL_TO_STR.split(',') if email.strip()] if EMAIL_TO_STR else []

# 验证必需配置
if not SERVER_IP:
    raise ValueError("环境变量 SERVER_IP 未设置，请在 .env 文件中配置")
if not SERVER_PORT:
    raise ValueError("环境变量 SERVER_PORT 未设置，请在 .env 文件中配置")
SERVER_PORT = int(SERVER_PORT)

if not MONGODB_HOST:
    raise ValueError("环境变量 MONGODB_HOST 未设置，请在 .env 文件中配置")

CONFIG = {

    # 模块信息
    "name": "市场分析报告生成模块",
    "description": "这是一个用于生成市场分析报告的模块",
    
    # 输入数据需求
    "input_data": [
        
    ],
    
    # 输出数据需求
    "output_data": [
        
    ]
}

