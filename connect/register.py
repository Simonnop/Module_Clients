"""
模块注册客户端
"""
import requests
import os
import logging
import hashlib
import importlib.util
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
current_dir = os.path.dirname(os.path.abspath(__file__))


def load_model_config():
    """
    加载数据需求配置
    
    Returns:
        数据需求配置
    """
    try:
        # 使用绝对路径导入配置文件
        config_path = os.path.join(current_dir, '../config/config.py')
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        return config_module.CONFIG
    except ImportError as e:
        logger.error(f"错误：无法导入配置文件: {e}")
        return None
    except Exception as e:
        logger.error(f"加载配置时发生错误: {e}")
        return None

def test_module_register():
    """
    测试模块注册
    """
    # 读取数据需求
    model_config = load_model_config()
    if not model_config:
        logger.error("无法获取数据需求配置，程序退出")
        return
    
    # 加载配置模块以获取服务器地址和端口
    try:
        import importlib.util
        config_path = os.path.join(current_dir, '../config/config.py')
        spec = importlib.util.spec_from_file_location("config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        server_ip = getattr(config_module, 'SERVER_IP')
        server_port = getattr(config_module, 'SERVER_PORT')
        
        if not server_ip:
            raise ValueError("配置文件中缺少 SERVER_IP")
        if server_port is None:
            raise ValueError("配置文件中缺少 SERVER_PORT")
    except Exception as e:
        logger.error(f"加载服务器配置时发生错误: {e}")
        raise
    
    # 设置请求URL
    endpoint = "/module/register"
    url = f"http://{server_ip}:{server_port}{endpoint}"

    # 为 main 文件夹计算一个 hash 值, 作为一个参数
    # 计算 main 文件夹的 hash 值
    execute_dir = os.path.join(current_dir, '../main')
    hash_obj = hashlib.md5()
    
    # 遍历文件夹中的所有文件
    for root, dirs, files in os.walk(execute_dir):
        for file in sorted(files):  # 排序以确保 hash 值稳定
            file_path = os.path.join(root, file)
            # 读取文件内容并更新 hash
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_obj.update(chunk)
                    
    execute_hash = hash_obj.hexdigest()
    logger.info(f"执行文件夹的 hash 值: {execute_hash}")
    
    # 设置请求参数
    params = {
        'name': model_config['name'],
        'description': model_config['description'],
        'input_data': json.dumps(model_config['input_data']),
        'output_data': json.dumps(model_config['output_data']),
        'modelHash': execute_hash
    }
    print(params)
    
    try:
        # 发送GET请求
        response = requests.get(url, params=params)
        
        # 检查响应状态码
        if response.status_code == 200:
            result = response.json()
            logger.info(result)
            hash_value = result['result']['hash']
            logger.info("注册成功！")
            logger.info(f"模块 Hash 值: {hash_value}")
            
            # 保存hash值到文件
            hash_file_path = os.path.join(current_dir, '../config/module_hash.txt')
            with open(hash_file_path, 'w') as f:
                f.write(hash_value)
            logger.info(f"Hash 值已保存到 {hash_file_path} 文件")
        else:
            logger.error(f"请求失败，状态码: {response.status_code}")
            logger.error(f"错误信息: {response.text}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"发生错误: {e}")

if __name__ == "__main__":
    test_module_register()

