"""
通用工具：环境加载、Mongo 连接、行情读取、邮件通知
"""
import atexit
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from pymongo import DESCENDING, MongoClient
from pymongo.errors import PyMongoError

# 环境与日志初始化
base_dir = Path(__file__).parent.parent
env_paths = [
    base_dir / '.env',
    base_dir / 'config' / '.env',
    Path(__file__).parent / '.env',
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mongo 配置
MONGODB_HOST = os.getenv('MONGODB_HOST')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'finance_data')
MONGODB_CLOSE_COLLECTION_NAME = os.getenv('MONGODB_CLOSE_COLLECTION_NAME', 'stock_close')
MONGODB_SIGNAL_COLLECTION_NAME = os.getenv('MONGODB_SIGNAL_COLLECTION_NAME', 'signal')
MONGODB_CURRENT_COLLECTION_NAME = os.getenv('MONGODB_CURRENT_COLLECTION_NAME', 'stock_current')
MONGODB_WATCH_COLLECTION_NAME = os.getenv('MONGODB_WATCH_COLLECTION_NAME', 'stock_watch')
MONGODB_MAX_POOL_SIZE = int(os.getenv('MONGODB_MAX_POOL_SIZE', '5'))

# 邮件配置
EMAIL_SEND_URL = os.getenv('EMAIL_SEND_URL', 'http://localhost:10101/send')
EMAIL_SEND_TIMEOUT = int(os.getenv('EMAIL_SEND_TIMEOUT', '10'))
EMAIL_SEND_CONTENT_TYPE = os.getenv('EMAIL_SEND_CONTENT_TYPE', 'text')

if not MONGODB_HOST:
    raise ValueError("环境变量 MONGODB_HOST 未设置，请在 .env 文件中配置")


class MongoConnectionManager:
    """MongoDB 单例连接管理"""

    _client: Optional[MongoClient] = None
    _db: Optional[Any] = None
    _collections: Dict[str, Any] = {}

    @classmethod
    def client(cls) -> MongoClient:
        if cls._client is None:
            try:
                cls._client = MongoClient(
                    MONGODB_HOST,
                    maxPoolSize=MONGODB_MAX_POOL_SIZE,
                    connect=False,
                    serverSelectionTimeoutMS=5000,
                    appname='module-clients-core'
                )
                logger.info(f"已连接到MongoDB数据库: {MONGODB_DB_NAME}")
            except PyMongoError as exc:
                logger.error(f"连接MongoDB失败: {exc}")
                raise
        return cls._client

    @classmethod
    def db(cls):
        if cls._db is None:
            cls._db = cls.client()[MONGODB_DB_NAME]
        return cls._db

    @classmethod
    def collection(cls, name: str):
        if name not in cls._collections:
            cls._collections[name] = cls.db()[name]
            logger.info(f"已初始化集合: {name}")
        return cls._collections[name]

    @classmethod
    def close(cls):
        if cls._client:
            try:
                cls._client.close()
                logger.info("MongoDB连接已关闭")
            except PyMongoError as exc:
                logger.debug(f"关闭MongoDB连接失败: {exc}")
            finally:
                cls._client = None
                cls._db = None
                cls._collections.clear()


def get_mongo_client():
    return MongoConnectionManager.client()


def get_mongo_db():
    return MongoConnectionManager.db()


def get_mongo_collection(collection_name: str):
    return MongoConnectionManager.collection(collection_name)


def close_mongo_connection():
    MongoConnectionManager.close()


atexit.register(close_mongo_connection)


def _normalize_stock_code(raw_code: Optional[str]) -> Optional[str]:
    """标准化股票代码，补齐市场前缀"""
    if not raw_code:
        return None

    sanitized = str(raw_code).strip().upper()
    if '.' in sanitized or '-' in sanitized:
        return sanitized

    digits = ''.join(filter(str.isdigit, sanitized))
    if len(digits) == 6:
        if digits.startswith('6'):
            return f'SH{digits}'
        if digits.startswith(('0', '3')):
            return f'SZ{digits}'

    return sanitized


def _build_stock_filter(stock_code: str) -> Dict[str, Any]:
    """构建通用的股票查询条件"""
    return {
        '$or': [
            {'stock_code': stock_code},
            {'symbol': stock_code},
            {'code': stock_code}
        ]
    }


def _extract_price_from_doc(doc: Dict[str, Any]) -> Optional[float]:
    """从文档中提取价格字段"""
    candidates = ('close', 'price', 'p', 'last', 'c', 'current', 'value')
    for key in candidates:
        if key in doc:
            try:
                return float(doc[key])
            except (TypeError, ValueError):
                continue
    return None


def fetch_close_history(stock_code: str, limit: int) -> List[float]:
    """从 close 集合获取历史收盘价"""
    collection = get_mongo_collection(MONGODB_CLOSE_COLLECTION_NAME)
    filter_query = _build_stock_filter(stock_code)
    cursor = collection.find(filter_query).sort([
        ('date', DESCENDING),
        ('_id', DESCENDING)
    ]).limit(limit)
    docs = list(cursor)

    if not docs:
        logger.warning(f"close 集合未找到 {stock_code} 的记录")
        return []

    docs.reverse()
    prices: List[float] = []
    for doc in docs:
        price = _extract_price_from_doc(doc)
        if price is not None:
            prices.append(price)

    return prices


def fetch_current_price(stock_code: str) -> Optional[float]:
    """获取 current 集合中最新的实时价格"""
    collection = get_mongo_collection(MONGODB_CURRENT_COLLECTION_NAME)
    filter_query = _build_stock_filter(stock_code)
    doc = collection.find_one(filter_query, sort=[('_id', DESCENDING)])
    if not doc:
        logger.warning(f"current 集合未找到 {stock_code} 的实时数据")
        return None
    return _extract_price_from_doc(doc)


def send_email_notification(subject: str, body: str, recipients: List[str]) -> bool:
    """通过 HTTP 服务发送邮件"""
    if not EMAIL_SEND_URL:
        logger.warning("未配置 EMAIL_SEND_URL，无法发送通知")
        return False

    clean_recipients = [addr.strip() for addr in recipients if isinstance(addr, str) and addr.strip()]
    if not clean_recipients:
        logger.warning("收件人列表为空，取消邮件发送")
        return False

    success = True
    for recipient in clean_recipients:
        payload = {
            "to_email": recipient,
            "subject": subject,
            "content": body,
            "content_type": EMAIL_SEND_CONTENT_TYPE
        }
        try:
            response = requests.post(EMAIL_SEND_URL, json=payload, timeout=EMAIL_SEND_TIMEOUT)
            response.raise_for_status()
            logger.info(f"已通过 HTTP 服务通知 {recipient}: {subject}")
        except Exception as exc:
            logger.error(f"调用邮件 HTTP 服务失败({recipient}): {exc}")
            success = False

    return success

