"""
股票实时数据获取模块 - 雪球 API
"""
import os
import requests
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
import pysnowball as ball

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
MONGODB_REALTIME_COLLECTION_NAME = os.getenv('MONGODB_REALTIME_COLLECTION_NAME', 'realtime')
MONGODB_CLOSE_COLLECTION_NAME = os.getenv('MONGODB_CLOSE_COLLECTION_NAME', 'close')

# MongoDB客户端（延迟初始化）
_mongo_client = None
_mongo_db = None
_collection_cache: Dict[str, Any] = {}

# 雪球 token（延迟初始化）
_xueqiu_token = None

# 验证必需配置
if not MONGODB_HOST:
    raise ValueError("环境变量 MONGODB_HOST 未设置，请在 .env 文件中配置")


def get_mongo_client():
    """
    获取MongoDB客户端（延迟初始化）
    
    Returns:
        MongoDB客户端对象
    """
    global _mongo_client
    
    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(MONGODB_HOST)
            logger.info(f"已连接到MongoDB数据库: {MONGODB_DB_NAME}")
        except Exception as e:
            logger.error(f"连接MongoDB失败: {e}")
            raise
    
    return _mongo_client


def get_mongo_db():
    """
    获取MongoDB数据库对象（延迟初始化）
    
    Returns:
        MongoDB数据库对象
    """
    global _mongo_db
    
    if _mongo_db is None:
        client = get_mongo_client()
        _mongo_db = client[MONGODB_DB_NAME]
    
    return _mongo_db


def get_mongo_collection(collection_name: str):
    """
    获取指定名称的 MongoDB 集合（缓存复用）
    """
    global _collection_cache

    if collection_name in _collection_cache:
        return _collection_cache[collection_name]

    db = get_mongo_db()
    collection = db[collection_name]
    _collection_cache[collection_name] = collection
    logger.info(f"已初始化集合: {collection_name}")
    return collection

def should_capture_close_snapshot(current_time: datetime) -> bool:
    """
    判断当前时间是否已经进入收盘后（下午3点及之后）
    """
    return current_time.hour >= 15


def persist_realtime_data(stock_data_list: List[Dict], timestamp: datetime) -> Tuple[int, int]:
    """
    使用 upsert 方式将实时数据写入实时集合
    """
    if not stock_data_list:
        return (0, 0)

    collection = get_mongo_collection(MONGODB_REALTIME_COLLECTION_NAME)
    success_count = 0
    fail_count = 0

    for stock_data in stock_data_list:
        stock_code = stock_data.get('stock_code')
        symbol = stock_data.get('symbol')
        code = stock_data.get('code')

        # 更新时匹配的字段：优先使用 stock_code，其次尝试 symbol/code
        if stock_code:
            filter_query = {'stock_code': stock_code}
        elif symbol:
            filter_query = {'symbol': symbol}
        elif code:
            filter_query = {'code': code}
        else:
            filter_query = None

        doc = stock_data.copy()
        doc['update_time'] = timestamp
        doc['date'] = timestamp.date()

        try:
            if filter_query:
                collection.replace_one(filter_query, doc, upsert=True)
            else:
                # 没有可用的唯一键，直接插入新文档
                collection.insert_one(doc)
            success_count += 1
        except Exception as exc:
            fail_count += 1
            logger.error(f"保存实时数据到 {MONGODB_REALTIME_COLLECTION_NAME} 失败 ({stock_code}): {exc}")

    logger.info(
        f"实时集合 {MONGODB_REALTIME_COLLECTION_NAME} 更新完成: 成功写入 {success_count} 条，失败 {fail_count} 条"
    )
    return success_count, fail_count


def persist_close_snapshot(stock_data_list: List[Dict]) -> Tuple[int, int]:
    """
    将收盘快照写入 close 表
    """
    if not stock_data_list:
        return (0, 0)

    collection = get_mongo_collection(MONGODB_CLOSE_COLLECTION_NAME)
    docs = []

    for stock_data in stock_data_list:
        doc = stock_data.copy()
        docs.append(doc)

    try:
        result = collection.insert_many(docs)
        success = len(result.inserted_ids)
        logger.info(f"收盘集合 {MONGODB_CLOSE_COLLECTION_NAME} 插入 {success} 条快照数据")
        return success, 0
    except Exception as exc:
        logger.error(f"保存收盘数据到 {MONGODB_CLOSE_COLLECTION_NAME} 失败: {exc}")
        return 0, len(docs)


def get_xueqiu_token() -> Optional[str]:
    """
    获取雪球 token
    
    Returns:
        token 字符串，如果获取失败则返回 None
    """
    global _xueqiu_token
    
    if _xueqiu_token is not None:
        return _xueqiu_token
    
    try:
        logger.info("正在获取雪球 token...")
        r = requests.get("https://xueqiu.com/hq", headers={"user-agent": "Mozilla"}, timeout=10)
        if 'xq_a_token' in r.cookies:
            _xueqiu_token = r.cookies["xq_a_token"]
            # 设置 pysnowball token
            ball.set_token(f'xq_a_token={_xueqiu_token}')
            logger.info("成功获取并设置雪球 token")
            return _xueqiu_token
        else:
            logger.error("未找到 xq_a_token cookie")
            return None
    except Exception as e:
        logger.error(f"获取雪球 token 失败: {e}")
        return None


def fetch_stock_data_batch(codes: List[str]) -> Tuple[Optional[List[Dict]], Optional[int]]:
    """
    批量获取股票的实时数据（使用雪球 API）
    
    Args:
        codes: 股票代码列表（如 ['SZ300750', 'SH600519']）
        
    Returns:
        (股票数据字典列表, HTTP状态码) 元组
        如果获取成功，返回 (stock_data_list, 200)
        如果获取失败，返回 (None, status_code)
    """
    # 确保 token 已获取
    token = get_xueqiu_token()
    if not token:
        logger.error("无法获取雪球 token")
        return (None, None)
    
    try:
        logger.info(f"正在批量获取 {len(codes)} 个股票的实时数据: {codes}")
        
        # 将股票代码列表转换为逗号分隔的字符串
        codes_str = ','.join(codes)
        
        # 调用 pysnowball quotec 接口获取实时行情
        result = ball.quotec(codes_str)
        
        if result is None:
            logger.error("雪球 API 返回 None")
            return (None, None)
        
        # 检查返回格式
        if isinstance(result, dict):
            # 如果返回的是字典，检查是否有 data 字段
            if 'data' in result:
                stock_data_list = result['data']
            elif 'list' in result:
                stock_data_list = result['list']
            else:
                # 直接使用字典本身
                stock_data_list = [result]
        elif isinstance(result, list):
            stock_data_list = result
        else:
            logger.error(f"雪球 API 返回格式异常，期望字典或列表，实际: {type(result)}")
            return (None, None)
        
        if not isinstance(stock_data_list, list):
            logger.error(f"股票数据格式异常，期望列表类型: {type(stock_data_list)}")
            return (None, None)
        
        logger.info(f"成功获取 {len(stock_data_list)} 条股票实时数据")
        return (stock_data_list, 200)
            
    except Exception as e:
        # 其他异常
        logger.error(f"获取股票数据时发生未预期的错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return (None, None)


def run(data, args=None):
    """
    执行业务逻辑的主函数
    
    Args:
        data: 输入数据字典（包含meta信息）
        args: 从服务器传入的参数字典，应包含code_list字段（股票代码列表）
        
    Returns:
        处理结果字典，包含获取到的股票数据
    """
    logger.info("=" * 60)
    logger.info("收到股票实时数据获取请求")
    logger.info(f"接收到的 data 参数: {json.dumps(data, ensure_ascii=False, indent=2)}")
    logger.info(f"接收到的 args 参数: {json.dumps(args if args else {}, ensure_ascii=False, indent=2)}")
    
    # 如果没有传入 args，使用空字典
    if args is None:
        args = {}
    
    # 获取股票代码列表
    code_list = args.get('code_list', [])
    
    if not code_list:
        logger.error("未提供股票代码列表")
        return {
            'status': 'error',
            'message': '缺少必需参数: code_list（股票代码列表）'
        }
    
    if not isinstance(code_list, list):
        logger.error(f"code_list 参数类型错误，期望列表，实际: {type(code_list)}")
        return {
            'status': 'error',
            'message': 'code_list 参数必须是列表类型'
        }
    
    logger.info(f"需要获取 {len(code_list)} 个股票的实时数据: {code_list}")
    
    # 存储获取到的数据（先不插入数据库）
    stock_data_list = []
    failed_stocks = []
    
    # 将股票代码转换为雪球格式（如 300750 -> SZ300750, 600519 -> SH600519）
    # 如果代码已经包含市场前缀，直接使用；否则根据代码判断
    codes = []
    for code in code_list:
        code_str = str(code).strip()
        # 如果代码以 SH/SZ 开头，直接使用
        if code_str.startswith('SH') or code_str.startswith('SZ'):
            codes.append(code_str)
        # 如果代码以 6 开头，认为是上海市场
        elif code_str.startswith('6'):
            codes.append(f'SH{code_str}')
        # 如果代码以 0/3 开头，认为是深圳市场
        elif code_str.startswith('0') or code_str.startswith('3'):
            codes.append(f'SZ{code_str}')
        else:
            # 默认尝试深圳市场
            codes.append(f'SZ{code_str}')
            logger.warning(f"无法判断股票代码 {code_str} 的市场，默认使用深圳市场")
    
    # 调用批量API获取数据
    result_data, status_code = fetch_stock_data_batch(codes)
    
    if result_data and status_code == 200:
        # 创建代码到数据的映射（使用 symbol 字段作为股票代码）
        code_to_data = {}
        for item in result_data:
            if isinstance(item, dict):
                symbol = item.get('symbol') or item.get('code')  # symbol 或 code 字段是股票代码
                if symbol:
                    code_to_data[symbol] = item
        
        # 将返回的数据与请求的代码列表匹配
        for code in codes:
            # 尝试直接匹配
            if code in code_to_data:
                stock_data = code_to_data[code].copy()
                # 添加股票代码字段（使用原始代码）
                stock_data['stock_code'] = code
                stock_data_list.append(stock_data)
            else:
                # 如果找不到匹配的数据，记录为失败
                failed_stocks.append(code)
                logger.warning(f"未找到股票代码 {code} 的数据")
    else:
        # API调用失败，所有股票都标记为失败
        failed_stocks = codes
        logger.error(f"批量获取股票数据失败，状态码: {status_code}")

    
    # 统一批量插入数据库
    if stock_data_list:
        store_time = datetime.now()
        success_count, fail_count = persist_realtime_data(stock_data_list, store_time)

        if should_capture_close_snapshot(store_time):
            close_success, close_fail = persist_close_snapshot(stock_data_list)
            if close_fail > 0:
                logger.warning(f"保存收盘快照时有 {close_fail} 条数据失败")
            else:
                logger.info(f"收盘快照保存完成，共 {close_success} 条")
    else:
        success_count = 0
        fail_count = 0
        logger.warning("没有成功获取到任何股票数据")
    
    # 构建返回结果（只返回执行状态，不返回数据）
    response = {
        'status': 'success',
        'total': len(code_list),
        'success_count': success_count,
        'failed_count': len(failed_stocks)
    }
    
    if failed_stocks:
        response['failed_stocks'] = failed_stocks
    
    logger.info(f"数据获取完成: 成功 {success_count}/{len(code_list)}, 失败 {len(failed_stocks)}")
    logger.info("=" * 60)
    
    return response

