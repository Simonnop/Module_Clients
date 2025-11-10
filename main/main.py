"""
业务执行模块
"""
import logging
import json
import requests
import simplejson
import os
import sys
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入配置和工具
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入配置模块
try:
    import importlib.util
    config_path = os.path.join(project_root, 'config', 'config.py')
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
except Exception as e:
    logger.error(f"无法导入配置模块: {e}")
    raise

# 导入城市坐标工具
from main.city_coordinates import batch_get_coordinates, get_city_coordinates

# MongoDB连接缓存（全局变量，复用连接）
_mongodb_client = None
_mongodb_collection = None
_index_created = False


def get_mongodb_client():
    """
    获取MongoDB客户端连接（复用连接）
    使用完整的连接字符串（mongodb+srv://格式）
    
    :return: MongoClient 实例
    """
    global _mongodb_client
    
    if _mongodb_client is None:
        try:
            connection_string = config.MONGODB_HOST
            
            if not connection_string.startswith('mongodb'):
                raise ValueError("MONGODB_HOST 必须是完整的 MongoDB 连接字符串（以 mongodb:// 或 mongodb+srv:// 开头）")
            
            # 优化连接池配置
            client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=10000,
                maxPoolSize=50,  # 最大连接池大小
                minPoolSize=5,   # 最小连接池大小
                maxIdleTimeMS=30000,  # 空闲连接超时时间
                connectTimeoutMS=10000,  # 连接超时时间
            )
            # 测试连接
            client.admin.command('ping')
            logger.info(f"成功连接到MongoDB")
            _mongodb_client = client
        except ConnectionFailure as e:
            logger.error(f"MongoDB连接失败: {e}")
            raise
    
    return _mongodb_client


def get_mongodb_collection():
    """
    获取MongoDB集合对象（复用集合对象）
    
    :return: Collection 对象
    """
    global _mongodb_collection, _index_created
    
    if _mongodb_collection is None:
        client = get_mongodb_client()
        db = client[config.MONGODB_DB]
        _mongodb_collection = db[config.MONGODB_COLLECTION]
    
    # 只在第一次创建索引（使用后台创建，不阻塞）
    if not _index_created:
        try:
            _mongodb_collection.create_index(
                [("city", 1), ("time", 1)],
                unique=True,
                background=True  # 后台创建索引，不阻塞其他操作
            )
            _index_created = True
            logger.info("MongoDB索引创建完成")
        except Exception as e:
            # 索引可能已存在，忽略错误
            if "already exists" not in str(e).lower() and "E11000" not in str(e):
                logger.warning(f"创建索引时出现警告: {e}")
            _index_created = True
    
    return _mongodb_collection


def batch_check_data_exists(collection, city, time_list):
    """
    批量检查数据是否已存在（优化性能）
    
    :param collection: MongoDB集合对象
    :param city: 城市名称
    :param time_list: 时间字符串列表
    :return: 已存在的时间集合
    """
    try:
        if not time_list:
            return set()
        
        # 批量查询已存在的记录
        existing_records = collection.find(
            {"city": city, "time": {"$in": time_list}},
            {"time": 1, "_id": 0}
        )
        
        # 提取已存在的时间
        existing_times = {record["time"] for record in existing_records}
        return existing_times
    except Exception as e:
        logger.error(f"批量检查数据是否存在时发生错误: {e}")
        return set()


def save_weather_data_to_mongodb(collection, city, weather_data):
    """
    保存天气数据到MongoDB数据库，如果已存在则跳过（优化版本）
    
    :param collection: MongoDB集合对象
    :param city: 城市名称
    :param weather_data: 天气数据字典
    :return: (插入数量, 跳过数量)
    """
    inserted_count = 0
    skipped_count = 0
    
    try:
        data_count = len(weather_data['time'])
        if data_count == 0:
            return 0, 0
        
        # 批量查询已存在的数据（性能优化）
        time_list = weather_data['time']
        existing_times = batch_check_data_exists(collection, city, time_list)
        
        # 过滤出需要插入的记录（排除已存在的）
        records_to_insert = []
        now = datetime.now()
        
        for i in range(data_count):
            time_str = weather_data['time'][i]
            if time_str not in existing_times:
                record = {
                    "city": city,
                    "time": time_str,
                    "baro": weather_data['baro'][i],
                    "cap": weather_data['cap'][i],
                    "dewPt": weather_data['dewPt'][i],
                    "temp": weather_data['temp'][i],
                    "utci": weather_data['utci'][i],
                    "vis": weather_data['vis'][i],
                    "windSpd": weather_data['windSpd'][i],
                    "windDir": weather_data['windDir'][i],
                    "cloudCover": weather_data['cloudCover'][i],
                    "created_at": now
                }
                records_to_insert.append(record)
            else:
                skipped_count += 1
        
        # 批量插入新数据
        if records_to_insert:
            try:
                result = collection.insert_many(records_to_insert, ordered=False)
                inserted_count = len(result.inserted_ids)
                logger.info(f"城市 '{city}' 成功插入 {inserted_count} 条新数据到MongoDB")
            except Exception as e:
                # 如果仍有重复键错误（并发情况），尝试逐条插入
                if "duplicate key" in str(e).lower() or "E11000" in str(e):
                    logger.info(f"检测到并发重复数据，开始逐条检查并插入...")
                    inserted_count = 0
                    skipped_count = data_count - len(records_to_insert)  # 重置跳过计数
                    for record in records_to_insert:
                        try:
                            collection.insert_one(record)
                            inserted_count += 1
                        except DuplicateKeyError:
                            skipped_count += 1
                        except Exception as insert_error:
                            logger.warning(f"插入单条数据失败: {insert_error}")
                            skipped_count += 1
                else:
                    raise
        
        return inserted_count, skipped_count
        
    except Exception as e:
        logger.error(f"保存天气数据到MongoDB失败: {e}")
        raise


def get_weather_data(latitude, longitude, api_key=None, app_id=None, days=10):
    """
    从MSN天气API获取天气数据
    
    :param latitude: 纬度
    :param longitude: 经度
    :param api_key: API密钥，如果为None则从配置读取
    :param app_id: 应用ID，如果为None则从配置读取
    :param days: 获取未来天数，默认10天
    :return: 包含天气数据的字典
    """
    if api_key is None:
        api_key = config.WEATHER_API_KEY
    if app_id is None:
        app_id = config.WEATHER_APP_ID
    
    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.41"
    }
    
    url = f'https://api.msn.cn/msn/v0/pages/weather/overview?apikey={api_key}&units=C&appId={app_id}&regionDataCount=20&days={days}&source=weather_csr&region=cn&market=zh-cn&locale=zh-cn&lat={latitude}&lon={longitude}'
    
    try:
        r = requests.get(url, headers=header, timeout=30)
        if r.status_code != 200:
            raise Exception(f"API请求失败，状态码: {r.status_code}")
        
        # 解析JSON数据
        response_data = simplejson.loads(r.content.decode(r.encoding))
        data = response_data['value'][0]['responses'][0]
        
        # 初始化数据字典
        all_datas = {
            'time': [],
            'baro': [],      # 气压
            'cap': [],       # 天气类型（文字描述）
            'dewPt': [],     # 露点
            'temp': [],      # 温度
            'utci': [],      # 体感温度
            'vis': [],       # 能见度
            'windSpd': [],   # 风速
            'windDir': [],   # 风向
            'cloudCover': [] # 云层厚度
        }
        
        # 获取当前天气（如果当前时间是整点，则包含）
        current = data['weather'][0]['current']
        current_time = current['created']
        # 检查当前时间是否为整点
        is_current_hourly = False
        if current_time:
            try:
                dt = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
                if dt.minute == 0:
                    is_current_hourly = True
            except (ValueError, AttributeError):
                if ':00:00' in str(current_time) or ':00Z' in str(current_time):
                    is_current_hourly = True
        
        # 只有当前时间是整点时才添加
        if is_current_hourly:
            all_datas['time'].append(current_time)
            for key in all_datas.keys():
                if key == 'time':
                    continue
                else:
                    all_datas[key].append(current.get(key, None))
        
        # 获取未来天气（在收集时就过滤非整点数据，优化性能）
        forecasts = data['weather'][0]['forecast']
        for d in range(min(days, len(forecasts.get('days', [])))):
            data_hourly = forecasts['days'][d].get('hourly', [])
            if not data_hourly:
                continue
            
            for hour_item in data_hourly:
                time_str = hour_item.get('valid', None)
                if not time_str:
                    continue
                
                # 检查是否为整点（在收集时就过滤，避免后续处理）
                is_hourly = False
                try:
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    if dt.minute == 0:
                        is_hourly = True
                except (ValueError, AttributeError):
                    if ':00:00' in str(time_str) or ':00Z' in str(time_str):
                        is_hourly = True
                
                # 只有整点数据才添加
                if is_hourly:
                    all_datas['time'].append(time_str)
                    for key in all_datas.keys():
                        if key != 'time':
                            all_datas[key].append(hour_item.get(key, None))
        
        logger.info(f"收集到 {len(all_datas['time'])} 条整点数据")
        return all_datas
    except Exception as e:
        logger.error(f"获取天气数据失败: {e}")
        raise




def run(data, args=None):
    """
    执行业务逻辑的主函数
    :param data: 输入数据字典
    :param args: 从服务器传入的参数字典，可选
    :return: 处理结果字典
    """
    # 记录收到的调用参数
    logger.info("=" * 60)
    logger.info("收到模块调用请求")
    logger.info(f"接收到的 data 参数: {json.dumps(data, ensure_ascii=False, indent=2)}")
    logger.info(f"接收到的 args 参数: {json.dumps(args if args else {}, ensure_ascii=False, indent=2)}")
    
    # 如果没有传入 args，使用空字典
    if args is None:
        args = {}
    
    try:
        # 获取城市列表
        city_list = args.get('city_list', [])
        if not city_list:
            raise ValueError("参数中缺少 city_list，请提供城市列表")
        
        if not isinstance(city_list, list):
            raise ValueError("city_list 必须是列表类型")
        
        logger.info(f"开始处理 {len(city_list)} 个城市的天气数据")
        
        # 获取城市坐标
        city_coords = batch_get_coordinates(city_list)
        if not city_coords:
            raise ValueError("未能获取任何城市的坐标信息")
        
        logger.info(f"成功获取 {len(city_coords)} 个城市的坐标")
        
        # 获取配置参数
        days = args.get('days', config.WEATHER_DAYS)
        
        # 获取MongoDB集合
        try:
            collection = get_mongodb_collection()
        except Exception as e:
            logger.error(f"无法连接到MongoDB: {e}")
            raise ValueError(f"MongoDB连接失败: {e}")
        
        # 处理每个城市（使用线程池并发处理，优化性能）
        results = {}
        failed_cities = []
        total_inserted = 0
        total_skipped = 0
        
        def process_city(city):
            """处理单个城市的天气数据"""
            try:
                coords = get_city_coordinates(city)
                if not coords:
                    logger.warning(f"跳过城市 '{city}'：未找到坐标信息")
                    return city, {
                        'status': 'failed',
                        'error': '未找到坐标信息'
                    }, True
                
                latitude, longitude = coords
                logger.info(f"正在获取城市 '{city}' (纬度: {latitude}, 经度: {longitude}) 的天气数据")
                
                # 获取天气数据
                weather_data = get_weather_data(latitude, longitude, days=days)
                
                # 保存数据到MongoDB（自动去重）
                inserted, skipped = save_weather_data_to_mongodb(collection, city, weather_data)
                
                logger.info(f"城市 '{city}' 处理完成: 插入 {inserted} 条，跳过 {skipped} 条（已存在）")
                
                return city, {
                    'status': 'success',
                    'inserted_count': inserted,
                    'skipped_count': skipped,
                    'total_data_count': len(weather_data['time'])
                }, False
                
            except Exception as e:
                logger.error(f"处理城市 '{city}' 时发生错误: {e}")
                return city, {
                    'status': 'failed',
                    'error': str(e)
                }, True
        
        # 使用线程池并发处理多个城市（最多5个并发，避免过多请求）
        max_workers = min(5, len(city_list))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_city = {executor.submit(process_city, city): city for city in city_list}
            
            for future in as_completed(future_to_city):
                city, result, is_failed = future.result()
                if is_failed:
                    failed_cities.append(city)
                results[city] = result
                
                if result and result.get('status') == 'success':
                    total_inserted += result.get('inserted_count', 0)
                    total_skipped += result.get('skipped_count', 0)
        
        # 构建返回结果
        reply = {
            'total_cities': len(city_list),
            'success_count': len(results) - len(failed_cities),
            'failed_count': len(failed_cities),
            'total_inserted': total_inserted,
            'total_skipped': total_skipped,
            'results': results
        }
        
        if failed_cities:
            reply['failed_cities'] = failed_cities
        
        logger.info(f"处理完成: 成功 {reply['success_count']} 个，失败 {reply['failed_count']} 个")
        logger.info(f"总计: 插入 {total_inserted} 条新数据，跳过 {total_skipped} 条重复数据")
        logger.info("=" * 60)
        
        return {
            'status': 'success',
            'reply': reply,
        }
        
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        logger.info("=" * 60)
        return {
            'status': 'error',
            'error': str(e),
        }

