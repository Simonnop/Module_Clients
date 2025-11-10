"""
业务执行模块
"""
import numpy as np
import logging
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    
    # 执行业务逻辑
    reply = args.get('print', 'args error')
    
    logger.info(f"执行结果: {reply}")
    logger.info("=" * 60)
    
    return {
        'status': 'success',
        'reply': reply,
    }

