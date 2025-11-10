"""
基金数据获取模块 - 必盈API
"""
import os
import requests
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
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

# 导入License管理模块
from license_manager import (
    get_available_license,
    rollback_license_usage,
    get_license_usage_count,
    initialize_license_usage,
    show_license_usage,
    get_licenses,
    get_daily_limit
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB配置（从环境变量读取）
MONGODB_HOST = os.getenv('MONGODB_HOST')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'forecast_platform')
MONGODB_COLLECTION_NAME = os.getenv('MONGODB_COLLECTION_NAME', 'fund_data')

# MongoDB客户端（延迟初始化）
_mongo_client = None
_mongo_db = None
_mongo_collection = None

# 必盈API配置（从环境变量读取）
BIYING_API_BASE_URL = os.getenv('BIYING_API_BASE_URL', 'http://api.biyingapi.com/fd/real/time')

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


def save_fund_data_to_mongodb(fund_data: Dict):
    """
    保存基金数据到MongoDB
    
    Args:
        fund_data: 基金数据字典
    """
    try:
        collection = get_mongo_collection()
        
        # 添加时间戳
        fund_data['create_time'] = datetime.now()
        
        # 插入数据
        result = collection.insert_one(fund_data)
        logger.info(f"成功保存基金 {fund_data.get('fund_code', 'unknown')} 的数据到MongoDB, ID: {result.inserted_id}")
        return True
        
    except Exception as e:
        logger.error(f"保存基金数据到MongoDB失败: {e}")
        return False


def fetch_fund_data(fund_code: str, license_key: str) -> Optional[Dict]:
    """
    获取单个基金的数据
    
    Args:
        fund_code: 基金代码（如159001）
        license_key: License密钥
        
    Returns:
        基金数据字典，如果获取失败则返回None
    """
    url = f"{BIYING_API_BASE_URL}/{fund_code}/{license_key}"
    today = datetime.now().date().isoformat()
    
    try:
        logger.info(f"正在获取基金 {fund_code} 的数据...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # License使用计数已在 get_available_license() 中通过事务更新
            # 这里只需要记录日志
            usage_count = get_license_usage_count(license_key, today)
            daily_limit = get_daily_limit(license_key)
            logger.info(f"成功获取基金 {fund_code} 的数据，License {license_key} 今日已使用 {usage_count}/{daily_limit} 次")
            return data
        else:
            # API调用失败，回滚License使用计数
            logger.error(f"获取基金 {fund_code} 数据失败，HTTP状态码: {response.status_code}, 响应: {response.text}")
            rollback_license_usage(license_key, today)
            return None
            
    except requests.exceptions.RequestException as e:
        # 请求异常，回滚License使用计数
        logger.error(f"请求基金 {fund_code} 数据时发生异常: {e}")
        rollback_license_usage(license_key, today)
        return None
    except json.JSONDecodeError as e:
        # JSON解析错误，回滚License使用计数
        logger.error(f"解析基金 {fund_code} 响应JSON时发生错误: {e}")
        rollback_license_usage(license_key, today)
        return None
    except Exception as e:
        # 其他异常，回滚License使用计数
        logger.error(f"获取基金 {fund_code} 数据时发生未预期的错误: {e}")
        rollback_license_usage(license_key, today)
        return None


def run(data, args=None):
    """
    执行业务逻辑的主函数
    
    Args:
        data: 输入数据字典（包含meta信息）
        args: 从服务器传入的参数字典，应包含code_list字段（基金代码列表）
        
    Returns:
        处理结果字典，包含获取到的基金数据
    """
    logger.info("=" * 60)
    logger.info("收到基金数据获取请求")
    logger.info(f"接收到的 data 参数: {json.dumps(data, ensure_ascii=False, indent=2)}")
    logger.info(f"接收到的 args 参数: {json.dumps(args if args else {}, ensure_ascii=False, indent=2)}")
    
    # 初始化License使用统计
    try:
        initialize_license_usage()
    except Exception as e:
        logger.warning(f"初始化License使用统计时出现警告: {e}")
    
    # 如果没有传入 args，使用空字典
    if args is None:
        args = {}
    
    # 获取基金代码列表
    code_list = args.get('code_list', [])
    
    if not code_list:
        logger.error("未提供基金代码列表")
        return {
            'status': 'error',
            'message': '缺少必需参数: code_list（基金代码列表）'
        }
    
    if not isinstance(code_list, list):
        logger.error(f"code_list 参数类型错误，期望列表，实际: {type(code_list)}")
        return {
            'status': 'error',
            'message': 'code_list 参数必须是列表类型'
        }
    
    logger.info(f"需要获取 {len(code_list)} 个基金的数据: {code_list}")
    
    # 存储获取结果
    results = []
    failed_funds = []
    
    # 遍历基金代码列表，获取每个基金的数据
    for fund_code in code_list:
        # 获取可用License
        license_key = get_available_license()
        
        if not license_key:
            logger.error(f"无法获取可用License，停止处理。已处理 {len(results)} 个基金")
            failed_funds.extend(code_list[len(results):])
            break
        
        # 获取基金数据
        fund_data = fetch_fund_data(str(fund_code), license_key)
        
        if fund_data:
            # 添加基金代码到数据中
            fund_data['fund_code'] = fund_code
            
            # 保存到MongoDB
            if save_fund_data_to_mongodb(fund_data):
                results.append(fund_code)
            else:
                failed_funds.append(fund_code)
                logger.warning(f"基金 {fund_code} 数据获取成功但保存到MongoDB失败")
        else:
            failed_funds.append(fund_code)
        
        # 添加短暂延迟，避免请求过快
        time.sleep(0.1)
    
    # 构建返回结果（只返回执行状态，不返回数据）
    response = {
        'status': 'success',
        'total': len(code_list),
        'success_count': len(results),
        'failed_count': len(failed_funds)
    }
    
    if failed_funds:
        response['failed_funds'] = failed_funds
    
    logger.info(f"数据获取完成: 成功 {len(results)}/{len(code_list)}, 失败 {len(failed_funds)}")
    logger.info("=" * 60)
    
    return response

