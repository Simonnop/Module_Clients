"""
License 管理模块
负责 License 的获取
使用 MongoDB 存储
"""
import os
import logging
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
logger = logging.getLogger(__name__)

if env_loaded:
    logger.debug(f"已加载 .env 文件")
else:
    logger.warning("未找到 .env 文件，将使用环境变量或默认值")

# MongoDB配置（从环境变量读取）
MONGODB_HOST = os.getenv('MONGODB_HOST')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'forecast_platform')
MONGODB_LICENSE_COLLECTION_NAME = os.getenv('MONGODB_LICENSE_COLLECTION_NAME', 'license_usage')

# 验证必需配置
if not MONGODB_HOST:
    raise ValueError("环境变量 MONGODB_HOST 未设置，请在 .env 文件中配置")

# License配置缓存（从数据库加载）
_licenses_cache = None

# MongoDB客户端（延迟初始化）
_mongo_client = None
_mongo_db = None
_license_collection = None


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


def get_license_collection():
    """
    获取License集合对象（延迟初始化）
    
    Returns:
        MongoDB集合对象
    """
    global _license_collection
    
    if _license_collection is None:
        db = get_mongo_db()
        _license_collection = db[MONGODB_LICENSE_COLLECTION_NAME]
        logger.info(f"已初始化License集合: {MONGODB_LICENSE_COLLECTION_NAME}")
    
    return _license_collection


def get_licenses_from_db() -> list:
    """
    从数据库获取所有License列表
    
    Returns:
        License列表
    """
    global _licenses_cache
    
    if _licenses_cache is None:
        try:
            collection = get_license_collection()
            # 获取所有唯一的license
            pipeline = [
                {"$group": {
                    "_id": "$license"
                }},
                {"$sort": {"_id": 1}}
            ]
            licenses = [doc["_id"] for doc in collection.aggregate(pipeline)]
            _licenses_cache = licenses
            logger.info(f"从数据库加载了 {len(licenses)} 个License")
            return licenses
        except Exception as e:
            logger.error(f"从数据库获取License列表失败: {e}")
            return []
    
    return _licenses_cache


def refresh_license_cache():
    """
    刷新License配置缓存（强制重新从数据库加载）
    """
    global _licenses_cache
    _licenses_cache = None
    logger.info("已刷新License配置缓存")


def get_licenses():
    """
    获取License列表
    
    Returns:
        License列表
    """
    return get_licenses_from_db()


# 模块导入时自动加载License列表
def _initialize_licenses():
    """
    初始化License列表（在模块导入时调用）
    """
    try:
        licenses = get_licenses_from_db()
        if licenses:
            logger.info(f"启动时已加载 {len(licenses)} 个License")
        else:
            logger.warning("启动时未找到任何License配置")
    except Exception as e:
        logger.warning(f"启动时加载License列表失败: {e}，将在首次使用时重试")


# 在模块导入时执行初始化
_initialize_licenses()

