"""
股票实时数据模块 - 策略调度器
"""
import importlib
import importlib.util
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 缓存 common 模块，避免重复加载
_common_module_cache = None


def _get_common():
    """延迟导入 common 模块，避免循环导入"""
    global _common_module_cache
    if _common_module_cache is not None:
        return _common_module_cache
    
    # 尝试标准包导入
    try:
        from main import common
        _common_module_cache = common
        return common
    except ImportError:
        pass
    
    # 如果包导入失败，直接加载 common.py 文件（适用于 spec_from_file_location 场景）
    try:
        current_dir = Path(__file__).parent
        common_path = current_dir / 'common.py'
        if common_path.exists():
            spec = importlib.util.spec_from_file_location("main.common", str(common_path))
            if spec and spec.loader:
                common_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(common_module)
                _common_module_cache = common_module
                return common_module
    except Exception as e:
        logger.error(f"加载 common 模块失败: {e}")
        raise ImportError(f"无法导入 common 模块: {e}") from e
    
    raise ImportError("无法找到 common 模块")

# 信号名称到策略模块的映射，新增策略时在此注册
STRATEGY_MODULES: Dict[str, str] = {
    'rsi': 'main.strategies.rsi',
    'ma_cross': 'main.strategies.ma_cross',
}


def load_watch_list(signal: Optional[str] = None) -> List[Dict[str, Any]]:
    """从 stock_watch 集合拉取待监控标的"""
    common = _get_common()
    collection = common.get_mongo_collection(common.MONGODB_WATCH_COLLECTION_NAME)
    query = {'signal': signal} if signal else {}
    docs = list(collection.find(query))

    items: List[Dict[str, Any]] = []
    for doc in docs:
        params = doc.get('params') or {}
        raw_code = doc.get('code') or doc.get('stock_code') or doc.get('symbol')
        stock_code = common._normalize_stock_code(raw_code)
        if not stock_code:
            logger.warning(f"跳过无效代码: {doc}")
            continue

        entry: Dict[str, Any] = {
            'signal': doc.get('signal'),
            'code': stock_code,
            'stock_code': stock_code,
            'symbol': stock_code,
            'name': doc.get('name'),
            'emails': doc.get('emails') or [],
            'params': params,
        }
        entry.update(params)  # 参数平铺到顶层，兼容旧策略入参
        items.append(entry)

    return items


def run_strategy(signal: str, items: List[Dict[str, Any]], data: Dict[str, Any]) -> Dict[str, Any]:
    """根据信号名称动态调度策略"""
    module_path = STRATEGY_MODULES.get(signal)
    if not module_path:
        raise ValueError(f"未配置的策略模块: {signal}")

    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        raise ImportError(f"加载策略模块失败 {module_path}: {exc}") from exc

    return module.run(data, {'items': items})


def run(data, args=None):
    """
    入口：按 stock_watch 表自动分发到各策略
    可选参数:
        - signal: 仅运行指定信号
    """
    signal_filter = None
    if isinstance(args, dict):
        signal_filter = args.get('signal')

    watch_items = load_watch_list(signal_filter)
    if not watch_items:
        logger.warning("stock_watch 集合未找到待监控标的")
        return {
            'status': 'error',
            'message': '未找到待监控标的'
        }

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in watch_items:
        signal = item.get('signal')
        if not signal:
            logger.warning(f"缺少 signal 字段，跳过: {item}")
            continue
        grouped[signal].append(item)

    results: Dict[str, Any] = {}
    errors: List[str] = []
    for signal, items in grouped.items():
        if not items:
            continue

        logger.info(f"调度策略 {signal}，标的数: {len(items)}")
        try:
            results[signal] = run_strategy(signal, items, data or {})
        except Exception as exc:
            logger.exception(f"执行策略 {signal} 失败: {exc}")
            errors.append(f"{signal}: {exc}")
            results[signal] = {
                'status': 'error',
                'message': str(exc)
            }

    status = 'success' if not errors else 'partial_success'
    return {
        'status': status,
        'executed_signals': list(grouped.keys()),
        'results': results,
        'errors': errors
    }
