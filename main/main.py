"""
股票实时数据模块
"""
import json
import logging
import os
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
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

# RSI 相关配置
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
RSI_HISTORY_DAYS = int(os.getenv('RSI_HISTORY_DAYS', str(max(RSI_PERIOD * 2, RSI_PERIOD + 1))))
RSI_STATE_FILE = base_dir / 'logs' / 'rsi_state.json'

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
                    appname='module-clients-rsi'
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


def load_rsi_state() -> Dict[str, Any]:
    """
    读取本地的 RSI 状态文件
    """
    if not RSI_STATE_FILE.exists():
        return {'date': '', 'history': {}, 'notifications': []}

    try:
        with open(RSI_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except Exception as exc:
        logger.warning(f"RSI 状态文件读取失败，将重建: {exc}")
        return {'date': '', 'history': {}, 'notifications': []}

    state.setdefault('history', {})
    state.setdefault('notifications', [])
    return state


def save_rsi_state(state: Dict[str, Any]) -> None:
    """
    将 RSI 状态保存到日志目录
    """
    filtered_history: Dict[str, List[float]] = {}
    for code, prices in state.get('history', {}).items():
        filtered_history[code] = prices[-RSI_HISTORY_DAYS:]

    serialized = {
        'date': state.get('date', ''),
        'history': filtered_history,
        'notifications': sorted(set(state.get('notifications', [])))
    }

    RSI_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(RSI_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning(f"保存 RSI 状态失败: {exc}")


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


def ensure_close_history(stock_code: str, state: Dict[str, Any], refresh_all: bool) -> List[float]:
    """
    确保 state 中缓存了当天的收盘价格
    """
    cached: List[float] = state.get('history', {}).get(stock_code, [])
    if refresh_all:
        history = fetch_close_history(stock_code, RSI_HISTORY_DAYS)
        if history:
            state.setdefault('history', {})[stock_code] = history
            return history
        return cached

    return cached

def compute_rsi_from_prices(price_series: Sequence[float], period=RSI_PERIOD):
    """
    计算RSI指标的辅助函数
    
    参数:
        price_series: 数值序列，价格序列（通常是收盘价）
        period: int, RSI计算周期，默认RSI_PERIOD
    
    返回:
        float | None: 最新一条RSI值，计算失败时返回None
    """

    # 计算RSI
    # 计算价格变化
    delta = pd.Series(price_series).diff()
    
    # 上涨和下跌分解
    gain = np.where(delta > 0, delta, 0)   # 上涨部分
    loss = np.where(delta < 0, -delta, 0)  # 下跌部分
    
    # 计算平均涨跌幅（简单移动平均版本）
    roll_gain = pd.Series(gain, index=pd.Series(price_series).index).rolling(
        window=period, min_periods=period
    ).mean()
    roll_loss = pd.Series(loss, index=pd.Series(price_series).index).rolling(
        window=period, min_periods=period
    ).mean()
    
    # 避免除零
    rs = roll_gain / roll_loss.replace(0, np.nan)
    
    # 计算RSI
    rsi = 100 - (100 / (1 + rs))
    
    # 获取当前时点的RSI值
    current_rsi = rsi.iloc[-1]

    logger.info(f"current_rsi: {current_rsi}")

    return current_rsi

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


def save_signal_notification(stock_code: str, display_name: str, alert_type: str, rsi_value: float, current_price: float, recipients: List[str]) -> None:
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
        'rsi': rsi_value,
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


def run_rsi_monitor(data: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    RSI 监控主逻辑
    """
    logger.info("进行 RSI 检测...")
    today = datetime.now().strftime('%Y-%m-%d')
    state = load_rsi_state()
    is_new_day = state.get('date') != today
    if is_new_day:
        logger.info(f"新的一天开始: {today}")
        state = {'date': today, 'history': {}, 'notifications': []}

    state['date'] = today

    notified_codes: Set[str] = set(state.get('notifications', []))
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    for entry in items:
        if not isinstance(entry, dict):
            msg = f"RSI 条目格式错误，期望字典，实际: {type(entry)}"
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

        logger.info(f"开始处理 {display_name} ({stock_code})")
        history = ensure_close_history(stock_code, state, is_new_day)
        if len(history) < RSI_PERIOD:
            msg = f"{stock_code} 历史收盘价不足 {RSI_PERIOD} 条，无法计算 RSI"
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
            msg = f"{stock_code} 当前价格无法获取，暂停 RSI 计算"
            logger.warning(msg)
            results.append({
                'code': stock_code,
                'name': display_name,
                'status': 'current_missing',
                'message': msg
            })
            continue

        price_sequence = history[-RSI_PERIOD:] + [current_price]
        rsi_value = compute_rsi_from_prices(price_sequence)
        if rsi_value is None:
            msg = f"{stock_code} RSI 计算失败"
            logger.warning(msg)
            results.append({
                'code': stock_code,
                'name': display_name,
                'status': 'rsi_failed',
                'message': msg
            })
            continue

        rsi_high = entry.get('rsi_high')
        rsi_low = entry.get('rsi_low')
        try:
            rsi_high = float(rsi_high) if rsi_high is not None else None
        except (TypeError, ValueError):
            rsi_high = None
        try:
            rsi_low = float(rsi_low) if rsi_low is not None else None
        except (TypeError, ValueError):
            rsi_low = None

        alert_type = None
        send_mail = False
        current_alert = None
        if rsi_high is not None and rsi_value >= rsi_high:
            alert_type = 'rsi_high'
            current_alert = f'RSI={rsi_value:.2f} 超过上限 {rsi_high}'
            send_mail = stock_code not in notified_codes
        elif rsi_low is not None and rsi_value <= rsi_low:
            alert_type = 'rsi_low'
            current_alert = f'RSI={rsi_value:.2f} 低于下限 {rsi_low}'
            send_mail = stock_code not in notified_codes

        notified_flag = False
        recipient_list = entry.get('emails') or []
        if isinstance(recipient_list, str):
            recipient_list = [item.strip() for item in recipient_list.split(',') if item.strip()]
        if send_mail and alert_type:
            subject = f"RSI 警示：{display_name} ({stock_code})"
            body = (
                f"{display_name} 的 RSI 值为 {rsi_value:.2f}，触发 {alert_type} 条件。\n"
                f"当前价格: {current_price}\n"
                f"时间: {datetime.now().isoformat()}\n"
                f"阈值设置：上限 {rsi_high}，下限 {rsi_low}"
            )
            notified_flag = send_email_notification(subject, body, recipient_list)
            if notified_flag:
                notified_codes.add(stock_code)
                save_signal_notification(stock_code, display_name, alert_type, rsi_value, current_price, recipient_list)
            else:
                current_alert = f"RSI {alert_type} 触发，但邮件发送失败"

        results.append({
            'code': stock_code,
            'name': display_name,
            'status': 'ok',
            'current_price': current_price,
            'rsi': round(rsi_value, 2),
            'alert': alert_type,
            'alert_message': current_alert,
            'notified': notified_flag
        })

    state['notifications'] = sorted(notified_codes)
    save_rsi_state(state)

    response = {
        'status': 'success',
        'type': 'rsi_monitor',
        'items': results,
        'errors': errors
    }
    return response


def run(data, args=None):
    """
    入口：仅执行 RSI 监控
    """
    if args is None:
        args = {}

    items = args.get('items')
    if not isinstance(items, list) or not items:
        logger.error("缺少有效的 args.items 参数，RSI 监控需要提供非空列表")
        return {
            'status': 'error',
            'message': '缺少非空的 args.items 参数'
        }

    return run_rsi_monitor(data, items)

