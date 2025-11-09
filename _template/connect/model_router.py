"""
请求处理模块，直接调用模块的 run 方法
"""
import json
import logging
import os
import sys
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 日志文件目录
LOG_DIR = os.path.join(os.path.dirname(__file__), '../logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 确保可以导入 execute 模块
execute_dir = os.path.join(os.path.dirname(__file__), '../execute')
if execute_dir not in sys.path:
    sys.path.insert(0, execute_dir)

# 导入 execute.main 模块
try:
    import importlib.util
    main_path = os.path.join(execute_dir, 'main.py')
    spec = importlib.util.spec_from_file_location("execute_main", main_path)
    execute_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execute_main)
    run = execute_main.run
except Exception as e:
    logger.error(f"无法导入 execute.main 模块: {e}")
    raise


def save_meta_log(meta):
    """
    保存 meta 信息到本地日志文件
    :param meta: 元信息字典
    """
    try:
        # 生成日志文件名（按日期）
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(LOG_DIR, f'execution_{today}.log')
        
        # 添加时间戳
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'meta': meta
        }
        
        # 追加写入日志文件
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        logger.debug(f"元信息已保存到日志文件: {log_file}")
    except Exception as e:
        logger.error(f"保存元信息日志失败: {e}")


def process_request(json_data):
    """
    处理业务请求的便捷函数，直接调用模块的 run 方法
    :param json_data: JSON格式的请求数据
    :return: 处理结果
    """
    try:
        # 解析JSON数据
        if isinstance(json_data, str):
            try:
                parsed_json = json.loads(json_data)
                message_data = parsed_json.get('message')
            except json.JSONDecodeError:
                logger.error("JSON解析失败")
                return {
                    'status': 'error',
                    'message': 'JSON格式错误'
                }
        else:
            message_data = json_data.get('message')

        # 解析 message 字段中的数据
        if isinstance(message_data, str):
            message_data = json.loads(message_data)
        
        # 提取执行数据和参数
        # 消息格式: {"type": "execute", "meta": {...}, "args": {...}}
        if not isinstance(message_data, dict) or message_data.get('type') != 'execute':
            logger.error(f"无效的消息格式: {message_data}")
            return {
                'status': 'error',
                'message': '无效的消息格式，期望 type 为 execute'
            }
        
        # 提取 meta 信息（用于日志记录）
        meta = message_data.get('meta', {})
        # 提取 args 参数（传入 run 方法）
        args = message_data.get('args', {})
        
        # 保存 meta 到本地日志文件
        save_meta_log(meta)
        
        # 准备传递给 run 方法的数据（可以包含 meta 信息，但主要使用 args）
        data = {
            'type': 'execute',
            'meta': meta,
        }
        
        logger.info(f"提取到参数: {args}")
        logger.info(f"执行元信息: {meta}")
        
        # 调用模块的 run 方法，传入 data 和 args
        logger.info("调用模块 run 方法")
        result = run(data, args=args)
        return result
        
    except Exception as e:
        logger.exception(f"处理请求时发生异常: {str(e)}")
        return {
            'status': 'error',
            'message': f'处理请求时发生异常: {str(e)}'
        }

