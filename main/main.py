"""
股票实时数据模块
"""
import json
import logging
import os
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import atexit
from dotenv import load_dotenv
from pymongo import DESCENDING, MongoClient
from pymongo.errors import PyMongoError
import numpy as np
import pandas as pd

# 加载 .env 文件（按优先级：项目根目录 -> config目录 -> main目录）
base_dir = Path(__file__).parent.parent
env_paths = [
    base_dir / '.env',                    # 项目根目录
    base_dir / 'config' / '.env',         # config目录
    Path(__file__).parent / '.env',       # main目录
]

env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        env_loaded = True
        break

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# MongoDB配置（从环境变量读取）
MONGODB_HOST = os.getenv('MONGODB_HOST')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'finance_data')
MONGODB_CLOSE_COLLECTION_NAME = os.getenv('MONGODB_CLOSE_COLLECTION_NAME', 'stock_close')
MONGODB_SIGNAL_COLLECTION_NAME = os.getenv('MONGODB_SIGNAL_COLLECTION_NAME', 'signal')
MONGODB_CURRENT_COLLECTION_NAME = os.getenv('MONGODB_CURRENT_COLLECTION_NAME', 'stock_current')
MONGODB_MAX_POOL_SIZE = int(os.getenv('MONGODB_MAX_POOL_SIZE', '5'))

# 双均线相关配置
MA_FAST_DEFAULT = int(os.getenv('MA_FAST_PERIOD', '5'))
MA_SLOW_DEFAULT = int(os.getenv('MA_SLOW_PERIOD', '20'))
MA_HISTORY_DAYS = int(os.getenv('MA_HISTORY_DAYS', str(max(MA_SLOW_DEFAULT * 2, MA_SLOW_DEFAULT + 5))))
MA_STATE_FILE = base_dir / 'logs' / 'ma_cross_state.json'

# 邮件通知配置（使用外部HTTP服务）
EMAIL_SEND_URL = os.getenv('EMAIL_SEND_URL', 'http://localhost:10101/send')
EMAIL_SEND_TIMEOUT = int(os.getenv('EMAIL_SEND_TIMEOUT', '10'))
EMAIL_SEND_CONTENT_TYPE = os.getenv('EMAIL_SEND_CONTENT_TYPE', 'text')

# 验证必需配置
if not MONGODB_HOST:
    raise ValueError("环境变量 MONGODB_HOST 未设置，请在 .env 文件中配置")


class MongoConnectionManager:
    """
    单例 MongoDB 连接管理类，避免高并发中频繁创建 client。
    """

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
                    appname='module-clients-ma-cross'
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
    """
    标准化股票代码，补齐市场前缀
    """
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
    """
    构建通用的股票查询条件
    """
    return {
        '$or': [
            {'stock_code': stock_code},
            {'symbol': stock_code},
            {'code': stock_code}
        ]
    }


def _extract_price_from_doc(doc: Dict[str, Any]) -> Optional[float]:
    """
    从文档中提取价格字段
    """
    candidates = ('close', 'price', 'p', 'last', 'c', 'current', 'value')
    for key in candidates:
        if key in doc:
            try:
                return float(doc[key])
            except (TypeError, ValueError):
                continue
    return None


def load_ma_state() -> Dict[str, Any]:
    """
    读取本地的双均线状态文件
    """
    if not MA_STATE_FILE.exists():
        return {'date': '', 'history': {}, 'notifications': {}}

    try:
        with open(MA_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except Exception as exc:
        logger.warning(f"双均线状态文件读取失败，将重建: {exc}")
        return {'date': '', 'history': {}, 'notifications': {}}

    state.setdefault('history', {})
    state.setdefault('notifications', {})
    return state


def save_ma_state(state: Dict[str, Any]) -> None:
    """
    将双均线状态保存到日志目录
    """
    filtered_history: Dict[str, List[float]] = {}
    for code, prices in state.get('history', {}).items():
        filtered_history[code] = prices[-MA_HISTORY_DAYS:]

    serialized = {
        'date': state.get('date', ''),
        'history': filtered_history,
        'notifications': state.get('notifications', {})
    }

    MA_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(MA_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning(f"保存双均线状态失败: {exc}")


def fetch_close_history(stock_code: str, limit: int) -> List[float]:
    """
    从 close 集合获取历史收盘价
    """
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
    """
    获取 current 集合中最新的实时价格
    """
    collection = get_mongo_collection(MONGODB_CURRENT_COLLECTION_NAME)
    filter_query = _build_stock_filter(stock_code)
    doc = collection.find_one(filter_query, sort=[('_id', DESCENDING)])
    if not doc:
        logger.warning(f"current 集合未找到 {stock_code} 的实时数据")
        return None
    return _extract_price_from_doc(doc)


def ensure_close_history(stock_code: str, state: Dict[str, Any], refresh_all: bool, history_days: int) -> List[float]:
    """
    确保 state 中缓存了当天的收盘价格
    """
    cached: List[float] = state.get('history', {}).get(stock_code, [])
    if refresh_all:
        history = fetch_close_history(stock_code, history_days)
        if history:
            state.setdefault('history', {})[stock_code] = history
            return history
        return cached

    return cached

def compute_ma_cross_signal(price_series: Sequence[float], fast_period: int, slow_period: int) -> Optional[Dict[str, float]]:
    """
    计算双均线交叉
    """
    if fast_period <= 0 or slow_period <= 0 or fast_period >= slow_period:
        return None

    if len(price_series) < slow_period + 1:
        return None

    series = pd.Series(price_series, dtype=float)
    fast_ma = series.rolling(window=fast_period, min_periods=fast_period).mean()
    slow_ma = series.rolling(window=slow_period, min_periods=slow_period).mean()

    prev_diff = fast_ma.iloc[-2] - slow_ma.iloc[-2]
    curr_diff = fast_ma.iloc[-1] - slow_ma.iloc[-1]
    if pd.isna(prev_diff) or pd.isna(curr_diff):
        return None

    cross = None
    if prev_diff < 0 <= curr_diff:
        cross = 'gold_cross'
    elif prev_diff > 0 >= curr_diff:
        cross = 'death_cross'

    return {
        'cross': cross,
        'fast_ma': float(fast_ma.iloc[-1]),
        'slow_ma': float(slow_ma.iloc[-1]),
        'prev_diff': float(prev_diff),
        'curr_diff': float(curr_diff)
    }

def send_email_notification(subject: str, body: str, recipients: List[str]) -> bool:
    """
    使用 HTTP 服务发送邮件通知
    """
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


def save_signal_notification(stock_code: str, display_name: str, alert_type: str, metric_value: float, current_price: float, recipients: List[str]) -> None:
    """
    将通知事件记录到 signal 集合，便于跨进程追踪和防止重复通知
    """
    if not MONGODB_SIGNAL_COLLECTION_NAME:
        return

    collection = get_mongo_collection(MONGODB_SIGNAL_COLLECTION_NAME)
    doc = {
        'stock_code': stock_code,
        'name': display_name,
        'alert_type': alert_type,
        'value': metric_value,
        'current_price': current_price,
        'recipients': recipients,
        'alert_time': datetime.now(),
        'alert_date': datetime.now().strftime('%Y-%m-%d')
    }

    try:
        collection.insert_one(doc)
        logger.info(f"已记录 signal 通知: {stock_code} {alert_type}")
    except Exception as exc:
        logger.warning(f"保存 signal 通知失败: {exc}")


def run_ma_cross_monitor(data: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    双均线监控主逻辑
    """
    logger.info("进行双均线检测...")
    today = datetime.now().strftime('%Y-%m-%d')
    state = load_ma_state()
    is_new_day = state.get('date') != today
    if is_new_day:
        logger.info(f"新的一天开始: {today}")
        state = {'date': today, 'history': {}, 'notifications': {}}

    state['date'] = today
    state.setdefault('notifications', {})
    state.setdefault('history', {})

    notified_map: Dict[str, str] = state.get('notifications', {})
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    for entry in items:
        if not isinstance(entry, dict):
            msg = f"双均线条目格式错误，期望字典，实际: {type(entry)}"
            logger.warning(msg)
            errors.append(msg)
            continue

        raw_code = entry.get('code') or entry.get('stock_code') or entry.get('symbol')
        stock_code = _normalize_stock_code(raw_code)
        display_name = entry.get('name') or stock_code or '未知标的'
        if not stock_code:
            error_msg = f"缺少有效的 code 字段，跳过条目: {entry}"
            logger.warning(error_msg)
            errors.append(error_msg)
            continue

        fast_period = entry.get('fast') or entry.get('ma_fast') or MA_FAST_DEFAULT
        slow_period = entry.get('slow') or entry.get('ma_slow') or MA_SLOW_DEFAULT
        try:
            fast_period = int(fast_period)
            slow_period = int(slow_period)
        except (TypeError, ValueError):
            msg = f"{stock_code} 周期配置无效 fast={fast_period}, slow={slow_period}"
            logger.warning(msg)
            errors.append(msg)
            continue

        if fast_period <= 0 or slow_period <= 0 or fast_period >= slow_period:
            msg = f"{stock_code} 周期配置不合理，需满足 0<fast<slow"
            logger.warning(msg)
            results.append({
                'code': stock_code,
                'name': display_name,
                'status': 'invalid_period',
                'message': msg
            })
            continue

        logger.info(f"开始处理 {display_name} ({stock_code}), fast={fast_period}, slow={slow_period}")
        history_need = max(MA_HISTORY_DAYS, slow_period + 1)
        history = ensure_close_history(stock_code, state, is_new_day, history_need)
        if len(history) < slow_period:
            msg = f"{stock_code} 历史收盘价不足 {slow_period} 条，无法计算均线"
            logger.warning(msg)
            results.append({
                'code': stock_code,
                'name': display_name,
                'status': 'history_missing',
                'message': msg
            })
            continue

        current_price = fetch_current_price(stock_code)
        if current_price is None:
            msg = f"{stock_code} 当前价格无法获取，暂停双均线计算"
            logger.warning(msg)
            results.append({
                'code': stock_code,
                'name': display_name,
                'status': 'current_missing',
                'message': msg
            })
            continue

        price_sequence = history[-(slow_period + 1):] + [current_price]
        ma_info = compute_ma_cross_signal(price_sequence, fast_period, slow_period)
        if ma_info is None:
            msg = f"{stock_code} 双均线计算失败"
            logger.warning(msg)
            results.append({
                'code': stock_code,
                'name': display_name,
                'status': 'ma_failed',
                'message': msg
            })
            continue

        cross_type = ma_info.get('cross')
        notified_flag = False
        alert_message = None
        recipient_list = entry.get('emails') or []
        if isinstance(recipient_list, str):
            recipient_list = [item.strip() for item in recipient_list.split(',') if item.strip()]

        if cross_type and notified_map.get(stock_code) != cross_type:
            subject = f"双均线信号：{display_name} ({stock_code})"
            body = (
                f"{display_name} 触发 {cross_type}。\n"
                f"fast={fast_period}, slow={slow_period}\n"
                f"MA_fast={ma_info.get('fast_ma'):.4f}, MA_slow={ma_info.get('slow_ma'):.4f}\n"
                f"当前价格: {current_price}\n"
                f"时间: {datetime.now().isoformat()}"
            )
            notified_flag = send_email_notification(subject, body, recipient_list)
            if notified_flag:
                notified_map[stock_code] = cross_type
                save_signal_notification(stock_code, display_name, cross_type, ma_info.get('curr_diff', 0.0), current_price, recipient_list)
            else:
                alert_message = f"{cross_type} 触发，但邮件发送失败"

        results.append({
            'code': stock_code,
            'name': display_name,
            'status': 'ok',
            'current_price': current_price,
            'fast_ma': round(ma_info.get('fast_ma', 0), 4),
            'slow_ma': round(ma_info.get('slow_ma', 0), 4),
            'diff': round(ma_info.get('curr_diff', 0), 4),
            'cross': cross_type,
            'alert_message': alert_message,
            'notified': notified_flag
        })

    state['notifications'] = notified_map
    save_ma_state(state)

    response = {
        'status': 'success',
        'type': 'ma_cross_monitor',
        'items': results,
        'errors': errors
    }
    return response


def run(data, args=None):
    """
    入口：执行双均线监控
    """
    if args is None:
        args = {}

    items = args.get('items')
    if not isinstance(items, list) or not items:
        logger.error("缺少有效的 args.items 参数，双均线监控需要提供非空列表")
        return {
            'status': 'error',
            'message': '缺少非空的 args.items 参数'
        }

    return run_ma_cross_monitor(data, items)

