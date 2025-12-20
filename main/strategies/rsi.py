"""
RSI 策略模块
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Sequence, Set

import numpy as np
import pandas as pd

from main import common

logger = logging.getLogger(__name__)

# RSI 配置
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
RSI_HISTORY_DAYS = int(os.getenv('RSI_HISTORY_DAYS', str(max(RSI_PERIOD * 2, RSI_PERIOD + 1))))
RSI_STATE_FILE = common.base_dir / 'logs' / 'rsi_state.json'


def load_rsi_state() -> Dict[str, Any]:
    """读取本地的 RSI 状态文件"""
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
    """保存 RSI 状态到日志目录"""
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


def ensure_close_history(stock_code: str, state: Dict[str, Any], refresh_all: bool) -> List[float]:
    """确保 state 中缓存了当天的收盘价格"""
    cached: List[float] = state.get('history', {}).get(stock_code, [])
    if refresh_all:
        history = common.fetch_close_history(stock_code, RSI_HISTORY_DAYS)
        if history:
            state.setdefault('history', {})[stock_code] = history
            return history
        return cached

    return cached


def compute_rsi_from_prices(price_series: Sequence[float], period=RSI_PERIOD):
    """计算 RSI 指标"""
    delta = pd.Series(price_series).diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    roll_gain = pd.Series(gain, index=pd.Series(price_series).index).rolling(
        window=period, min_periods=period
    ).mean()
    roll_loss = pd.Series(loss, index=pd.Series(price_series).index).rolling(
        window=period, min_periods=period
    ).mean()

    rs = roll_gain / roll_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    logger.info(f"current_rsi: {current_rsi}")
    return current_rsi


def save_signal_notification(stock_code: str, display_name: str, alert_type: str, rsi_value: float, current_price: float, recipients: List[str]) -> None:
    """将通知事件记录到 signal 集合"""
    if not common.MONGODB_SIGNAL_COLLECTION_NAME:
        return

    collection = common.get_mongo_collection(common.MONGODB_SIGNAL_COLLECTION_NAME)
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
    """RSI 监控主逻辑"""
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
        stock_code = common._normalize_stock_code(raw_code)
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

        current_price = common.fetch_current_price(stock_code)
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
            notified_flag = common.send_email_notification(subject, body, recipient_list)
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
    """入口：执行 RSI 策略"""
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


