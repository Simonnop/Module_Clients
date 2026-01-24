"""
业务执行模块
"""
import numpy as np
import logging
import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pymongo
from pymongo import MongoClient
import requests
from premailer import Premailer

# 导入配置
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import (
    MONGODB_HOST, MONGODB_DATABASE, MONGODB_COLLECTION_BILI, MONGODB_COLLECTION_BYDOC,
    FILTER_NAMES, LLM_API_URL, LLM_MODEL, LLM_ENABLE_SEARCH,
    EMAIL_API_URL, EMAIL_TO
)

# 导入模板
# 使用绝对导入，因为模块可能被动态加载
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    # 尝试使用绝对导入
    from templates import build_llm_prompt, get_email_html_template
except ImportError:
    # 如果失败，使用 importlib 动态加载
    import importlib.util
    templates_path = current_dir / 'templates.py'
    if templates_path.exists():
        spec = importlib.util.spec_from_file_location("templates", templates_path)
        templates_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(templates_module)
        build_llm_prompt = templates_module.build_llm_prompt
        get_email_html_template = templates_module.get_email_html_template
    else:
        raise ImportError(f"无法找到 templates 模块: {templates_path}")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建线程池执行器用于后台执行任务
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="market_analysis")


def get_target_date():
    """获取目标日期（前一天）"""
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day - 1

    # 处理跨月跨年的情况
    if day <= 0:
        # 如果前一天是上个月的最后一天
        if month == 1:
            # 跨年
            year -= 1
            month = 12
            day = 31
        else:
            # 跨月
            month -= 1
            # 获取上个月的最后一天
            if month in [1, 3, 5, 7, 8, 10, 12]:
                day = 31
            elif month in [4, 6, 9, 11]:
                day = 30
            else:  # 2月
                # 判断是否为闰年
                if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                    day = 29
                else:
                    day = 28

    return f"{year}-{month:02d}-{day:02d}"


def build_name_filter(filter_names):
    """构建名称筛选条件"""
    return {
        "$or": [
            {"name": {"$regex": name}} for name in filter_names
        ]
    }


def query_mongodb_data(target_date, name_filter, bili_collection, bydoc_collection):
    """从 MongoDB 查询数据"""
    # 在 bili_info 集合中查找该日期且 name 匹配的数据
    query_bili = {"used": False, **name_filter}
    bili_results = list(bili_collection.find(query_bili))
    logger.info(f"bili_info 集合中找到 {len(bili_results)} 条")

    # 在 bydoc_info 集合中查找该日期且 name 匹配的数据
    query_bydoc = {"used": False, **name_filter}
    bydoc_results = list(bydoc_collection.find(query_bydoc))
    logger.info(f"bydoc_info 集合中找到 {len(bydoc_results)} 条")

    # 将已查询到的文档的 "used" 字段设置为 True
    if bili_results:
        for doc in bili_results:
            bili_collection.update_one(
                {"_id": doc["_id"]}, {"$set": {"used": True}}
            )

    if bydoc_results:
        for doc in bydoc_results:
            bydoc_collection.update_one(
                {"_id": doc["_id"]}, {"$set": {"used": True}}
            )

    return bili_results, bydoc_results


def format_content_text(target_date, bili_results, bydoc_results):
    """整理查询到的内容为文本格式"""
    content_text = f"日期: {target_date}\n\n"

    # 整理 bili_info 的内容
    if bili_results:
        content_text += "=== B站视频和动态内容 ===\n\n"
        for i, doc in enumerate(bili_results, 1):
            content_text += f"【{doc.get('name', 'N/A')}】({doc.get('type', 'N/A')})\n"
            content_text += f"时间: {doc.get('time', 'N/A')}\n"
            content_text += f"URL: {doc.get('url', 'N/A')}\n"
            content_text += f"内容: {doc.get('content', 'N/A')}\n\n"

    # 整理 bydoc_info 的内容
    if bydoc_results:
        content_text += "=== PDF文档内容 ===\n\n"
        for i, doc in enumerate(bydoc_results, 1):
            content_text += f"【{doc.get('name', 'N/A')}】({doc.get('type', 'N/A')})\n"
            content_text += f"时间: {doc.get('time', 'N/A')}\n"
            content_text += f"URL: {doc.get('url', 'N/A')}\n"
            content_text += f"内容: {doc.get('content', 'N/A')}\n\n"

    return content_text




def call_llm_api(question, api_url, model, enable_search):
    """调用 LLM API"""
    logger.info("正在调用大语言模型进行总结...")
    resp = requests.post(
        api_url,
        json={
            "question": question,
            "model": model,
            "enable_search": enable_search
        }
    )
    
    if resp.status_code == 200:
        try:
            response_data = resp.json()
            if response_data.get('success') and 'data' in response_data:
                return response_data['data'].get('answer', '')
            else:
                logger.error("LLM API 响应格式异常")
                return None
        except Exception as e:
            logger.error(f"解析 LLM API 响应失败: {e}")
            return None
    else:
        logger.error(f"LLM API 请求失败，状态码: {resp.status_code}")
        return None


def process_html_for_email(html_body, target_date):
    """处理 HTML 使其邮件兼容"""
    # 将 SVG 图标替换为 emoji（邮件兼容性）
    # 替换宏观维度解析的 SVG 图标为图表 emoji
    html_body = re.sub(
        r'<svg[^>]*viewBox="0 0 20 20"[^>]*><path[^>]*d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z"[^>]*></path></svg>',
        '<span style="font-size: 18px; margin-right: 8px;">📊</span>',
        html_body
    )
    # 替换核心关注标的的 SVG 图标为闪电 emoji
    html_body = re.sub(
        r'<svg[^>]*viewBox="0 0 20 20"[^>]*><path[^>]*fill-rule="evenodd"[^>]*d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z"[^>]*></path></svg>',
        '<span style="font-size: 18px; margin-right: 8px;">⚡</span>',
        html_body
    )
    # 通用替换：替换所有剩余的 SVG 标签（兜底处理）
    html_body = re.sub(
        r'<svg[^>]*>.*?</svg>',
        '',
        html_body,
        flags=re.DOTALL
    )
    
    # 移除 json-mini 部分（邮件中不需要 JSON 数据）
    html_body = re.sub(
        r'<div[^>]*class="json-mini"[^>]*>.*?</div>',
        '',
        html_body,
        flags=re.DOTALL
    )
    
    # 构建完整的 HTML 文档
    html_template = get_email_html_template(target_date, html_body)
    
    # 使用 premailer 将样式内联化（邮件兼容）
    try:
        # 抑制 cssutils 的警告和错误日志
        import cssutils
        import logging as cssutils_logging
        cssutils_log = cssutils_logging.getLogger('CSSUTILS')
        original_level = cssutils_log.level
        cssutils_log.setLevel(cssutils_logging.CRITICAL)  # 只显示严重错误
        
        p = Premailer(html_template, base_url=None, remove_classes=False, strip_important=False, keep_style_tags=True)
        email_html = p.transform()
        
        # 恢复原始日志级别
        cssutils_log.setLevel(original_level)
        
        logger.info("已使用 premailer 处理 HTML 邮件兼容性")
        return email_html
    except ImportError:
        logger.warning("premailer 未安装，使用原始 HTML（可能邮件兼容性较差）")
        return html_template
    except Exception as e:
        logger.warning(f"邮件兼容处理出错: {e}，使用原始 HTML")
        return html_template


def send_email(email_html, target_date, api_url, to_email_list):
    """发送邮件到多个邮箱"""
    if not email_html:
        logger.error("无法获取 HTML 内容，无法发送邮件")
        return False
    
    if not to_email_list:
        logger.warning("邮箱列表为空，跳过邮件发送")
        return False
    
    success_count = 0
    fail_count = 0
    
    for to_email in to_email_list:
        data = {
            "to_email": to_email,
            "subject": f'市场分析报告 | {datetime.now().strftime("%Y-%m-%d")}',
            "content": email_html,
            "content_type": "html"
        }
        
        try:
            response = requests.post(api_url, json=data)
            result = response.json()
            if result.get('success'):
                logger.info(f"邮件发送成功到 {to_email}: {result}")
                success_count += 1
            else:
                logger.error(f"邮件发送失败到 {to_email}: {result}")
                fail_count += 1
        except Exception as e:
            logger.error(f"发送邮件到 {to_email} 失败: {e}")
            fail_count += 1
    
    logger.info(f"邮件发送完成: 成功 {success_count} 个，失败 {fail_count} 个")
    return success_count > 0


def _run_sync(data, args=None):
    """
    执行业务逻辑的同步函数（内部使用）
    :param data: 输入数据字典
    :param args: 从服务器传入的参数字典，可选
    :return: 处理结果字典
    """
    logger.info("=" * 60)
    logger.info("开始执行市场分析报告生成任务（后台线程）")
    
    try:
        # 获取目标日期（前一天）
        target_date = get_target_date()
        logger.info(f"开始处理日期: {target_date}")
        
        # 连接 MongoDB
        logger.info("正在连接 MongoDB...")
        client = MongoClient(MONGODB_HOST)
        db = client[MONGODB_DATABASE]
        bili_collection = db[MONGODB_COLLECTION_BILI]
        bydoc_collection = db[MONGODB_COLLECTION_BYDOC]
        
        # 查看集合信息
        bili_count = bili_collection.count_documents({})
        bydoc_count = bydoc_collection.count_documents({})
        logger.info(f"bili_info 集合文档数量: {bili_count}")
        logger.info(f"bydoc_info 集合文档数量: {bydoc_count}")
        
        # 构建名称筛选条件
        name_filter = build_name_filter(FILTER_NAMES)
        
        # 查询数据
        bili_results, bydoc_results = query_mongodb_data(
            target_date, name_filter, bili_collection, bydoc_collection
        )
        
        # 检查是否两个结果都为空（包括空列表的情况）
        if (not bili_results or len(bili_results) == 0) and (not bydoc_results or len(bydoc_results) == 0):
            logger.warning(f"未找到 {target_date} 的数据，bili_results 和 bydoc_results 都为空列表，放弃执行")
            logger.info("=" * 60)
            return {
                'status': 'skipped',
                'target_date': target_date,
                'message': '未找到数据，放弃执行',
                'bili_count': 0,
                'bydoc_count': 0
            }
        
        # 整理内容
        content_text = format_content_text(target_date, bili_results, bydoc_results)
        
        # 构建 LLM 提示词
        question = build_llm_prompt(target_date, content_text)
        
        # 调用 LLM API
        html_body = call_llm_api(
            question, 
            LLM_API_URL, 
            LLM_MODEL, 
            LLM_ENABLE_SEARCH
        )
        
        if not html_body:
            logger.error("LLM API 调用失败，无法生成报告")
            return {
                'status': 'error',
                'message': 'LLM API 调用失败'
            }
        
        # 处理 HTML 使其邮件兼容
        email_html = process_html_for_email(html_body, target_date)
        
        # 保存邮件兼容版本（可选）
        email_output_path = f"summarize_{target_date}_email.html"
        try:
            with open(email_output_path, "w", encoding="utf-8") as f:
                f.write(email_html)
            logger.info(f"已保存邮件兼容版本到: {email_output_path}")
        except Exception as e:
            logger.warning(f"保存 HTML 文件失败: {e}")
        
        # 发送邮件
        if EMAIL_TO and len(EMAIL_TO) > 0:
            send_success = send_email(
                email_html, 
                target_date, 
                EMAIL_API_URL, 
                EMAIL_TO
            )
            if send_success:
                logger.info("邮件发送成功")
            else:
                logger.warning("邮件发送失败")
        else:
            logger.warning("未配置收件人邮箱列表，跳过邮件发送")
        
        logger.info("=" * 60)
        
        return {
            'status': 'success',
            'target_date': target_date,
            'bili_count': len(bili_results),
            'bydoc_count': len(bydoc_results),
            'email_sent': len(EMAIL_TO) > 0 if EMAIL_TO else False,
            'html_saved': email_output_path
        }
        
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e)
        }


def run(data, args=None):
    """
    执行业务逻辑的主函数（异步后台执行）
    :param data: 输入数据字典
    :param args: 从服务器传入的参数字典，可选
    :return: 立即返回任务已提交的响应
    """
    logger.info("提交市场分析报告生成任务到后台线程池")
    
    # 提交任务到线程池异步执行
    future = _executor.submit(_run_sync, data, args)
    
    # 立即返回，不等待任务完成
    return {
        'status': 'submitted',
        'message': '任务已提交到后台执行',
        'task_id': id(future)
    }
