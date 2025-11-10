"""
城市坐标转换工具
提供城市名称到经纬度的映射
"""
import logging

logger = logging.getLogger(__name__)

# 中国主要城市坐标映射（纬度, 经度）
CITY_COORDINATES = {
    # 湖北省城市
    "孝感": (30.9246, 113.9169),
    "宜昌": (30.7026, 111.2865),
    "武汉": (30.5928, 114.3055),
    "荆州": (30.3352, 112.2397),
    "荆门": (31.0354, 112.1994),
    "襄阳": (32.0088, 112.1224),
    "随州": (31.6901, 113.3825),
    "黄冈": (30.4539, 114.8724),
    
    # 其他常见城市（可根据需要扩展）
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "成都": (30.6624, 104.0633),
    "重庆": (29.5630, 106.5516),
    "西安": (34.3416, 108.9398),
    "南京": (32.0603, 118.7969),
    "天津": (39.3434, 117.2008),
}


def get_city_coordinates(city_name):
    """
    根据城市名称获取经纬度坐标
    
    :param city_name: 城市名称（字符串）
    :return: (latitude, longitude) 元组，如果城市不存在则返回 None
    """
    city_name = city_name.strip()
    
    # 直接查找
    if city_name in CITY_COORDINATES:
        return CITY_COORDINATES[city_name]
    
    # 尝试添加"市"后缀查找
    if city_name + "市" in CITY_COORDINATES:
        return CITY_COORDINATES[city_name + "市"]
    
    # 尝试去除"市"后缀查找
    if city_name.endswith("市"):
        city_without_suffix = city_name[:-1]
        if city_without_suffix in CITY_COORDINATES:
            return CITY_COORDINATES[city_without_suffix]
    
    logger.warning(f"未找到城市 '{city_name}' 的坐标信息")
    return None


def batch_get_coordinates(city_list):
    """
    批量获取城市坐标
    
    :param city_list: 城市名称列表
    :return: 字典，格式为 {城市名: (纬度, 经度)}，未找到的城市不包含在结果中
    """
    result = {}
    for city in city_list:
        coords = get_city_coordinates(city)
        if coords:
            result[city] = coords
        else:
            logger.warning(f"跳过城市 '{city}'：未找到坐标信息")
    return result

