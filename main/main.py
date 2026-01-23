"""
业务执行模块 - 百度云盘文件下载和处理
"""
import asyncio
import aiohttp
import aiofiles
import logging
import json
import os
import sys
import threading
from datetime import datetime
from bypy import ByPy
import pymongo

# 添加 config 目录到路径
config_dir = os.path.join(os.path.dirname(__file__), '../config')
if config_dir not in sys.path:
    sys.path.insert(0, config_dir)

from config import LLM_API_URL, MONGODB_URI, MONGODB_DATABASE

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def process_pdf_file(session, file_path, filename, year, month, day, now, url):
    """
    异步处理单个 PDF 文件
    """
    try:
        async with aiofiles.open(file_path, "rb") as f:
            file_content = await f.read()
            
            data = aiohttp.FormData()
            data.add_field('question', 
                          "Convert the file content into text, output the original text without summarizing or generalizing, disregard K-line charts and tables, remove advertisements and irrelevant content at the end, and eliminate line breaks. Simply output the text content directly. Always response in 中文")
            data.add_field('files', file_content, filename=filename, content_type='application/pdf')
            
            async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=600)) as response:
                if response.status == 200:
                    result = await response.json()
                    answer = result.get("data", {}).get("answer", "")
                    
                    item = {
                        "name": filename[:4],
                        "type": "PDF",
                        "url": file_path,
                        "time": now.strftime("%H:%M:%S"),
                        "date": f"{year}-{month:02d}-{day:02d}",
                        "content": answer
                    }
                    logger.info(f"处理完成: {filename}")
                    return item
                else:
                    logger.error(f"处理失败 {filename}: HTTP {response.status}")
                    return None
    except Exception as e:
        logger.error(f"处理文件 {filename} 时出错: {e}")
        return None


async def main_async():
    """
    异步主函数 - 后台执行百度云盘文件下载和处理
    """
    try:
        # 初始化百度云盘客户端
        bp = ByPy()
        
        # 获取当前日期（前一天）
        now = datetime.now()
        year = now.year
        month = now.month
        day = now.day - 1
        
        logger.info(f"开始处理日期: {year}-{month:02d}-{day:02d}")
        
        # 构建文件夹名称
        folder_name = f'老王知识库文集{str(year)[2:4]}年{month:02d}月{day:02d}日'
        
        # 列出文件夹中的文件
        bp.list(folder_name)
        files = bp.file_list
        
        if not files:
            logger.warning(f"文件夹 {folder_name} 中没有找到文件")
            return {
                'status': 'success',
                'message': f'文件夹 {folder_name} 中没有找到文件'
            }
        
        logger.info(f"找到 {len(files)} 个文件")
        
        # 下载符合条件的 PDF 文件
        download_dir = f"{year}-{month:02d}-{day:02d}"
        os.makedirs(download_dir, exist_ok=True)
        
        downloaded_files = []
        for i in files:
            file_name = i.split(' ')[1]
            if file_name.endswith('.pdf') and '鉴茶' in file_name:
                logger.info(f"下载文件: {file_name}")
                bp.downfile(folder_name + '/' + file_name, f"{year}-{month:02d}-{day:02d}" + '/' + file_name)
                downloaded_files.append(file_name)
        
        logger.info(f"共下载 {len(downloaded_files)} 个文件")
        
        if not downloaded_files:
            logger.warning("没有符合条件的文件需要处理")
            return {
                'status': 'success',
                'message': '没有符合条件的文件需要处理'
            }
        
        # 异步处理 PDF 文件
        url = LLM_API_URL
        results_json = []
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for filename in downloaded_files:
                file_path = os.path.join(download_dir, filename)
                if os.path.isfile(file_path):
                    task = process_pdf_file(session, file_path, filename, year, month, day, now, url)
                    tasks.append(task)
            
            # 并发处理所有文件
            results = await asyncio.gather(*tasks)
            results_json = [r for r in results if r is not None]
        
        logger.info(f"共处理 {len(results_json)} 个文件")
        
        # # 保存结果到 JSON 文件
        # output_file = f"results_{year}-{month:02d}-{day:02d}.json"
        # async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
        #     await f.write(json.dumps(results_json, ensure_ascii=False, indent=2))
        # logger.info(f"结果已保存到: {output_file}")   
        
        # 插入数据到 MongoDB
        if results_json:
            try:
                client = pymongo.MongoClient(MONGODB_URI)
                db = client[MONGODB_DATABASE]
                collection = db['bydoc_info']
                
                result = collection.insert_many(results_json)
                logger.info(f"数据导入完成，成功插入 {len(result.inserted_ids)} 条记录到 bydoc_info 表")
                client.close()
            except Exception as e:
                logger.error(f"插入数据时出错: {e}")
        
        return {
            'status': 'success',
            'message': f'处理完成，共处理 {len(results_json)} 个文件',
            'processed_count': len(results_json)
        }
        
    except Exception as e:
        logger.exception(f"执行过程中发生错误: {e}")
        return {
            'status': 'error',
            'message': f'执行失败: {str(e)}'
        }


def run(data, args=None):
    """
    执行业务逻辑的主函数 - 后台异步执行
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
    
    # 在后台线程中异步执行主逻辑
    def run_async_task():
        """在后台线程中运行异步任务"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(main_async())
            loop.close()
            logger.info(f"后台任务执行完成: {result}")
        except Exception as e:
            logger.exception(f"后台异步任务执行错误: {e}")
    
    # 启动后台线程执行任务
    thread = threading.Thread(target=run_async_task, daemon=True)
    thread.start()
    
    logger.info("任务已在后台异步执行")
    logger.info("=" * 60)
    
    return {
        'status': 'success',
        'message': '任务已在后台异步执行'
    }

