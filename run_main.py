#!/usr/bin/env python3
"""
直接运行 main 函数的脚本
"""
import os
import sys
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入 main 模块的 run 函数
from main.main import run

def main():
    """
    主函数：直接调用 run 函数
    """
    # 默认参数配置
    # 可以通过命令行参数或环境变量修改
    default_city_list = '北京,上海,广州,深圳'
    default_days = 10
    
    # 从环境变量获取
    env_city_list = os.getenv('CITY_LIST', default_city_list)
    env_days = os.getenv('DAYS', str(default_days))
    
    # 如果提供了命令行参数，使用命令行参数（优先级最高）
    if len(sys.argv) > 1:
        city_list_str = sys.argv[1]
    else:
        city_list_str = env_city_list
    
    if len(sys.argv) > 2:
        days_str = sys.argv[2]
    else:
        days_str = env_days
    
    # 处理城市列表：去除空白字符，过滤空字符串
    city_list = [city.strip() for city in city_list_str.split(',') if city.strip()]
    
    if not city_list:
        print("错误: 城市列表不能为空")
        print("使用方法: python3 run_main.py [城市列表] [天数]")
        print("示例: python3 run_main.py 北京,上海,广州 10")
        sys.exit(1)
    
    # 处理天数：验证范围
    try:
        days = int(days_str)
        if days < 1:
            print(f"警告: 天数 {days} 小于 1，已调整为 1")
            days = 1
        elif days > 30:
            print(f"警告: 天数 {days} 大于 30，已调整为 30")
            days = 30
    except ValueError:
        print(f"错误: 天数参数 '{days_str}' 不是有效的数字")
        sys.exit(1)
    
    # 准备参数
    data = {}  # 根据实际需求设置
    args = {
        'city_list': city_list,
        'days': days
    }
    
    print(f"开始运行，城市列表: {', '.join(city_list)}, 天数: {days}")
    print("=" * 60)
    
    # 调用 run 函数
    result = run(data, args)
    
    # 打印结果
    print("\n" + "=" * 60)
    print("运行结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 根据结果返回退出码
    if result.get('status') == 'success':
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()

