"""
License 管理模块
负责 License 的获取、使用次数统计和更新
使用 MongoDB 存储，支持事务保证并发安全
"""
import os
import logging
import time
from datetime import datetime
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure

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

# License轮换索引（本地缓存，用于轮换选择）
current_license_index = 0

# License配置缓存（从数据库加载）
_licenses_cache = None
_license_limits_cache = None

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
    获取License使用统计集合对象（延迟初始化）
    
    Returns:
        MongoDB集合对象
    """
    global _license_collection
    
    if _license_collection is None:
        db = get_mongo_db()
        _license_collection = db[MONGODB_LICENSE_COLLECTION_NAME]
        
        # 创建唯一索引确保 (license, date) 唯一
        _license_collection.create_index(
            [("license", 1), ("date", 1)],
            unique=True,
            name="license_date_unique"
        )
        logger.info(f"已初始化License统计集合: {MONGODB_LICENSE_COLLECTION_NAME}")
    
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


def get_license_limit(license_key: str) -> int:
    """
    从数据库获取指定License的每日限额
    
    Args:
        license_key: License密钥
        
    Returns:
        每日限额，如果未找到则返回默认值200
    """
    global _license_limits_cache
    
    if _license_limits_cache is None:
        _license_limits_cache = {}
    
    if license_key not in _license_limits_cache:
        try:
            collection = get_license_collection()
            # 获取该License的最新记录（包含limit字段）
            doc = collection.find_one(
                {"license": license_key},
                sort=[("date", -1)]
            )
            
            if doc and "limit" in doc:
                limit = doc["limit"]
                _license_limits_cache[license_key] = limit
                logger.info(f"License {license_key[:20]}... 的限额: {limit}")
                return limit
            else:
                # 如果数据库中没有limit字段，使用默认值200
                default_limit = 200
                _license_limits_cache[license_key] = default_limit
                logger.warning(f"License {license_key[:20]}... 未找到limit字段，使用默认值: {default_limit}")
                return default_limit
        except Exception as e:
            logger.error(f"从数据库获取License限额失败: {e}")
            return 200
    
    return _license_limits_cache[license_key]


def refresh_license_cache():
    """
    刷新License配置缓存（强制重新从数据库加载）
    """
    global _licenses_cache, _license_limits_cache
    _licenses_cache = None
    _license_limits_cache = None
    logger.info("已刷新License配置缓存")


def initialize_license_usage():
    """
    初始化License使用统计（如果不存在则创建）
    """
    try:
        collection = get_license_collection()
        today = datetime.now().date().isoformat()
        licenses = get_licenses_from_db()
        
        if not licenses:
            logger.warning("未找到任何License配置，请先在数据库中添加License记录")
            return
        
        for license_key in licenses:
            # 获取该License的limit
            limit = get_license_limit(license_key)
            
            # 使用 upsert 确保每个 License 都有当天的记录
            collection.update_one(
                {"license": license_key, "date": today},
                {
                    "$setOnInsert": {
                        "license": license_key,
                        "date": today,
                        "usage_count": 0,
                        "limit": limit,
                        "last_updated": datetime.now()
                    }
                },
                upsert=True
            )
    except Exception as e:
        logger.error(f"初始化License使用统计失败: {e}")


def reset_daily_usage_if_needed():
    """
    检查并重置每日使用计数（如果需要）
    使用事务确保原子性
    """
    try:
        collection = get_license_collection()
        today = datetime.now().date().isoformat()
        
        # 获取所有 License 的最新日期
        pipeline = [
            {"$group": {
                "_id": "$license",
                "latest_date": {"$max": "$date"}
            }}
        ]
        
        latest_dates = {}
        for doc in collection.aggregate(pipeline):
            latest_dates[doc["_id"]] = doc["latest_date"]
        
        # 获取所有License列表
        licenses = get_licenses_from_db()
        
        if not licenses:
            logger.warning("未找到任何License配置")
            return
        
        # 如果某个 License 的最新日期不是今天，需要初始化今天的记录
        need_reset = False
        for license_key in licenses:
            if license_key not in latest_dates or latest_dates[license_key] != today:
                need_reset = True
                break
        
        if need_reset:
            client = get_mongo_client()
            
            # 使用事务重置
            with client.start_session() as session:
                with session.start_transaction():
                    for license_key in licenses:
                        # 获取该License的limit
                        limit = get_license_limit(license_key)
                        
                        # 确保今天的记录存在
                        collection.update_one(
                            {"license": license_key, "date": today},
                            {
                                "$setOnInsert": {
                                    "license": license_key,
                                    "date": today,
                                    "usage_count": 0,
                                    "limit": limit,
                                    "last_updated": datetime.now()
                                }
                            },
                            upsert=True,
                            session=session
                        )
                    session.commit_transaction()
            logger.info(f"已重置License使用统计，当前日期: {today}")
    except Exception as e:
        logger.error(f"重置License使用统计失败: {e}")


def get_license_usage_count(license_key: str, date: str) -> int:
    """
    获取指定License在指定日期的使用次数
    
    Args:
        license_key: License密钥
        date: 日期字符串（ISO格式）
        
    Returns:
        使用次数
    """
    try:
        collection = get_license_collection()
        doc = collection.find_one({"license": license_key, "date": date})
        return doc["usage_count"] if doc else 0
    except Exception as e:
        logger.error(f"获取License使用次数失败: {e}")
        return 0


def rollback_license_usage(license_key: str, date: str):
    """
    回滚License使用计数（当API调用失败时使用）
    使用事务确保原子性
    
    Args:
        license_key: License密钥
        date: 日期字符串（ISO格式）
    """
    try:
        collection = get_license_collection()
        client = get_mongo_client()
        
        with client.start_session() as session:
            with session.start_transaction():
                # 减少使用计数（但不能小于0）
                # 注意：这里不需要 upsert，因为回滚时文档应该已经存在
                result = collection.update_one(
                    {"license": license_key, "date": date, "usage_count": {"$gt": 0}},
                    {
                        "$inc": {"usage_count": -1},
                        "$set": {"last_updated": datetime.now()}
                    },
                    session=session
                )
                
                if result.modified_count > 0:
                    session.commit_transaction()
                    logger.info(f"已回滚License {license_key} 的使用计数")
                else:
                    session.abort_transaction()
                    logger.warning(f"无法回滚License {license_key} 的使用计数（可能计数已为0）")
    except OperationFailure as e:
        # MongoDB操作失败（可能包括写冲突）
        if "WriteConflict" in str(e) or "write conflict" in str(e).lower():
            logger.warning(f"回滚License {license_key} 使用计数时发生写冲突")
        else:
            logger.error(f"回滚License使用计数时发生操作失败: {e}")
    except Exception as e:
        logger.error(f"回滚License使用计数失败: {e}")


def get_available_license() -> Optional[str]:
    """
    获取可用的License（轮换使用，考虑每日限额）
    使用事务确保并发安全
    
    Returns:
        可用的License字符串，如果所有License都达到限额则返回None
    """
    global current_license_index
    
    # 确保License统计已初始化
    reset_daily_usage_if_needed()
    
    # 从数据库获取License列表
    licenses = get_licenses_from_db()
    
    if not licenses:
        logger.error("未找到任何License配置")
        return None
    
    today = datetime.now().date().isoformat()
    collection = get_license_collection()
    client = get_mongo_client()
    
    # 确保索引在有效范围内
    if current_license_index >= len(licenses):
        current_license_index = 0
    
    # 尝试找到可用的License
    start_index = current_license_index
    attempts = 0
    
    while attempts < len(licenses):
        license_key = licenses[current_license_index]
        daily_limit = get_license_limit(license_key)
        
        # 使用事务检查和预留License
        try:
            with client.start_session() as session:
                with session.start_transaction():
                    # 读取当前使用次数
                    doc = collection.find_one(
                        {"license": license_key, "date": today},
                        session=session
                    )
                    
                    current_count = doc["usage_count"] if doc else 0
                    
                    # 检查是否可用
                    if current_count < daily_limit:
                        # 预留License（增加计数）
                        if doc is None:
                            # 文档不存在，创建新文档并设置初始值
                            collection.update_one(
                                {"license": license_key, "date": today},
                                {
                                    "$setOnInsert": {
                                        "license": license_key,
                                        "date": today,
                                        "usage_count": 1,
                                        "limit": daily_limit,
                                        "last_updated": datetime.now()
                                    }
                                },
                                upsert=True,
                                session=session
                            )
                        else:
                            # 文档存在，使用 $inc 增加计数
                            collection.update_one(
                                {"license": license_key, "date": today},
                                {
                                    "$inc": {"usage_count": 1},
                                    "$set": {"last_updated": datetime.now()}
                                },
                                session=session
                            )
                        session.commit_transaction()
                        
                        # 找到可用License，更新索引以便下次轮换
                        current_license_index = (current_license_index + 1) % len(licenses)
                        new_count = current_count + 1
                        logger.info(f"成功获取License {license_key}，今日已使用 {new_count}/{daily_limit} 次")
                        return license_key
                    else:
                        # License已用完，回滚事务
                        session.abort_transaction()
        except OperationFailure as e:
            # MongoDB操作失败（可能包括写冲突或字段冲突）
            error_msg = str(e).lower()
            if "write conflict" in error_msg or "writeconflict" in error_msg or "conflict" in error_msg:
                # 发生写冲突或字段冲突，重试
                logger.warning(f"获取License {license_key} 时发生冲突，重试中... (错误: {e})")
                time.sleep(0.01)  # 短暂等待后重试
                continue
            else:
                logger.error(f"获取License {license_key} 时发生操作失败: {e}")
        except Exception as e:
            logger.error(f"获取License {license_key} 时发生错误: {e}")
        
        # 当前License不可用，尝试下一个
        current_license_index = (current_license_index + 1) % len(licenses)
        attempts += 1
    
    # 所有License都达到限额
    logger.error("所有License都已达到每日限额")
    return None


def show_license_usage():
    """
    显示当前所有License的使用情况
    """
    try:
        collection = get_license_collection()
        today = datetime.now().date().isoformat()
        licenses = get_licenses_from_db()
        
        if not licenses:
            print("\n未找到任何License配置\n")
            return
        
        print("\n" + "=" * 60)
        print(f"License 使用统计（日期: {today}）")
        print("=" * 60)
        
        for license_key in licenses:
            doc = collection.find_one({"license": license_key, "date": today})
            usage_count = doc["usage_count"] if doc else 0
            daily_limit = get_license_limit(license_key)
            remaining = max(0, daily_limit - usage_count)
            print(f"License: {license_key[:20]}...")
            print(f"  已使用: {usage_count}/{daily_limit}")
            print(f"  剩余: {remaining}")
            print()
        
        print("=" * 60 + "\n")
    except Exception as e:
        logger.error(f"显示License使用统计失败: {e}")


# 为了向后兼容，提供LICENSES和DAILY_LIMIT的访问接口
def get_licenses():
    """
    获取License列表（向后兼容）
    
    Returns:
        License列表
    """
    return get_licenses_from_db()


def get_daily_limit(license_key: str = None) -> int:
    """
    获取每日限额（向后兼容）
    如果未指定license_key，返回第一个License的限额
    
    Args:
        license_key: License密钥（可选）
        
    Returns:
        每日限额
    """
    licenses = get_licenses_from_db()
    if not licenses:
        return 200
    
    if license_key:
        return get_license_limit(license_key)
    else:
        return get_license_limit(licenses[0])


# 向后兼容：提供函数形式的访问接口
# 注意：LICENSES 和 DAILY_LIMIT 不再是常量，请使用 get_licenses() 和 get_daily_limit() 函数

