"""
股票实时交易数据获取模块 - Infoway API
"""
import os
import requests
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

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
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'forecast_platform')
MONGODB_COLLECTION_NAME = os.getenv('MONGODB_COLLECTION_NAME', 'stock_data')

# MongoDB客户端（延迟初始化）
_mongo_client = None
_mongo_db = None
_mongo_collection = None

# Infoway API配置（从环境变量读取）
INFOWAY_API_BASE_URL = os.getenv('INFOWAY_API_BASE_URL', 'https://data.infoway.io')
INFOWAY_API_KEY = os.getenv('INFOWAY_API_KEY')

# 验证必需配置
if not MONGODB_HOST:
    raise ValueError("环境变量 MONGODB_HOST 未设置，请在 .env 文件中配置")
if not INFOWAY_API_KEY:
    raise ValueError("环境变量 INFOWAY_API_KEY 未设置，请在 .env 文件中配置")


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


def get_mongo_collection():
    """
    获取MongoDB集合对象（延迟初始化）
    
    Returns:
        MongoDB集合对象
    """
    global _mongo_collection
    
    if _mongo_collection is None:
        db = get_mongo_db()
        _mongo_collection = db[MONGODB_COLLECTION_NAME]
        logger.info(f"已初始化集合: {MONGODB_COLLECTION_NAME}")
    
    return _mongo_collection

def save_stock_data_batch_to_mongodb(stock_data_list: List[Dict]) -> tuple:
    """
    批量保存股票数据到MongoDB
    
    Args:
        stock_data_list: 股票数据字典列表
        
    Returns:
        (成功数量, 失败数量) 元组
    """
    if not stock_data_list:
        return (0, 0)
    
    try:
        collection = get_mongo_collection()
        
        # 添加时间戳
        now = datetime.now()
        for stock_data in stock_data_list:
            stock_data['create_time'] = now
        
        # 批量插入数据
        result = collection.insert_many(stock_data_list)
        logger.info(f"成功批量保存 {len(result.inserted_ids)} 条股票数据到MongoDB")
        return (len(result.inserted_ids), 0)
        
    except Exception as e:
        logger.error(f"批量保存股票数据到MongoDB失败: {e}")
        return (0, len(stock_data_list))


def fetch_stock_data_batch(codes: List[str]) -> Tuple[Optional[List[Dict]], Optional[int]]:
    """
    批量获取股票的实时交易数据
    
    Args:
        codes: 股票代码列表（如 ['TSLA.US', 'AAPL.US']）
        
    Returns:
        (股票数据字典列表, HTTP状态码) 元组
        如果获取成功，返回 (stock_data_list, 200)
        如果获取失败，返回 (None, status_code)
    """
    # 将股票代码列表转换为逗号分隔的字符串
    codes_str = ','.join(codes)
    url = f"{INFOWAY_API_BASE_URL}/stock/batch_trade/{codes_str}"
    
    # 设置请求头
    headers = {
        'apiKey': INFOWAY_API_KEY
    }
    
    try:
        logger.info(f"正在批量获取 {len(codes)} 个股票的实时交易数据: {codes_str}")
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # 检查返回格式：{ret: 200, msg: "success", traceId: "...", data: [...]}
            if not isinstance(data, dict):
                logger.error(f"API返回数据格式异常，期望字典类型: {type(data)}")
                return (None, response.status_code)
            
            ret = data.get('ret')
            if ret != 200:
                logger.error(f"API返回错误，ret: {ret}, msg: {data.get('msg')}")
                return (None, response.status_code)
            
            # 获取数据列表
            stock_data_list = data.get('data', [])
            if not isinstance(stock_data_list, list):
                logger.error(f"API返回data字段格式异常，期望列表类型: {type(stock_data_list)}")
                return (None, response.status_code)
            
            logger.info(f"成功获取 {len(stock_data_list)} 条股票实时交易数据")
            return (stock_data_list, 200)
        else:
            # API调用失败
            logger.error(f"批量获取股票数据失败，HTTP状态码: {response.status_code}, 响应: {response.text}")
            return (None, response.status_code)
            
    except requests.exceptions.RequestException as e:
        # 请求异常
        logger.error(f"请求股票数据时发生异常: {e}")
        return (None, None)
    except json.JSONDecodeError as e:
        # JSON解析错误
        logger.error(f"解析响应JSON时发生错误: {e}")
        return (None, None)
    except Exception as e:
        # 其他异常
        logger.error(f"获取股票数据时发生未预期的错误: {e}")
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
    logger.info("收到股票实时交易数据获取请求")
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
    
    logger.info(f"需要获取 {len(code_list)} 个股票的实时交易数据: {code_list}")
    
    # 存储获取到的数据（先不插入数据库）
    stock_data_list = []
    failed_stocks = []
    
    # 批量获取股票数据
    # 将股票代码列表转换为字符串列表（确保格式正确）
    codes = [str(code)+".SH" for code in code_list] + [str(code)+".SZ" for code in code_list]
    
    # 调用批量API获取数据
    result_data, status_code = fetch_stock_data_batch(codes)
    
    if result_data and status_code == 200:
        # 创建代码到数据的映射（使用 s 字段作为标的名称）
        code_to_data = {}
        for item in result_data:
            symbol = item.get('s')  # s 字段是标的名称
            if symbol:
                code_to_data[symbol] = item
        
        # 将返回的数据与请求的代码列表匹配
        for code in codes:
            # 尝试直接匹配
            if code in code_to_data:
                stock_data = code_to_data[code].copy()
                # 添加股票代码字段（使用原始代码）
                stock_data['stock_code'] = code
                # 字段映射：保持原有字段名，同时添加中文注释
                # s: 标的名称, t: 交易时间, p: 价格, v: 成交量, vw: 成交额, td: 交易方向
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
        logger.info(f"开始批量插入 {len(stock_data_list)} 条股票数据到数据库...")
        success_count, fail_count = save_stock_data_batch_to_mongodb(stock_data_list)
        
        if fail_count > 0:
            logger.warning(f"批量插入时有 {fail_count} 条数据插入失败")
    else:
        success_count = 0
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

