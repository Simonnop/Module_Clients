"""
命令行脚本：批量获取股票实时数据并输出字段列表，用于测试或调试。
"""
import argparse
import logging
import json
from datetime import datetime
from typing import List, Dict, Any

from main.main import fetch_stock_data_batch

def map_stock_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    将原始股票数据映射到目标数据结构
    """
    timestamp = data.get('timestamp')
    date_str = None
    if timestamp:
        try:
            # timestamp is in milliseconds
            dt = datetime.fromtimestamp(timestamp / 1000)
            date_str = dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    import pysnowball as ball
    import requests
    r = requests.get("https://xueqiu.com/hq", headers={"user-agent": "Mozilla"})
    t = r.cookies["xq_a_token"]
    # print(t)
    ball.set_token(f'xq_a_token={t}')
    name = ball.suggest_stock(data.get('symbol'))['data'][0]['query']

    return {
        "code": data.get('symbol'),
        "name": name,  # 原始数据中可能不包含名称
        "date": date_str,
        "timestamp": timestamp,
        "open": data.get('open'),
        "high": data.get('high'),
        "low": data.get('low'),
        "close": data.get('current'),
        "volume": data.get('volume'),
        "change_percent": data.get('percent'),
        "turnover_rate": data.get('turnover_rate')
    }

def get_stock_field_names(stock_data_list: List[Dict]) -> List[str]:
    """
    提取股票数据字典中的字段名称（去重并排序），用于测试验证字段结构。
    """
    field_names = set()
    for record in stock_data_list:
        if isinstance(record, dict):
            field_names.update(record.keys())

    return sorted(field_names)

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试雪球实时数据字段")
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='限制测试时使用的股票数量（默认10）'
    )
    parser.add_argument(
        '--codes',
        type=str,
        default='',
        help='逗号分隔的股票代码列表（如 SH600519,SZ000001），未提供则使用默认样例。'
    )
    return parser.parse_args()


def parse_codes(codes_str: str) -> List[str]:
    if not codes_str:
        return []

    return [code.strip() for code in codes_str.split(',') if code.strip()]


def main():
    configure_logging()
    args = parse_args()

    input_codes = parse_codes(args.codes)
    if not input_codes:
        input_codes = ['SH600519']
        logging.info("未提供预置代码，使用默认样例 ['SH600519']")

    sample_codes = input_codes[: args.limit]
    logging.info(f"使用 {len(sample_codes)} 个代码测试：{sample_codes}")

    stock_data_list, status_code = fetch_stock_data_batch(sample_codes)
    fields = get_stock_field_names(stock_data_list if stock_data_list else [])

    if status_code != 200 or not stock_data_list:
        logging.error(f"未成功获取数据，状态码：{status_code}")
        return

    logging.info(f"获取到 {len(stock_data_list)} 条股票数据，字段如下：")
    print(json.dumps(fields, ensure_ascii=False, indent=2))

    logging.info("首条数据预览：")
    print(json.dumps(stock_data_list[0], ensure_ascii=False, indent=2))

    logging.info("映射后的数据预览：")
    mapped_data = map_stock_data(stock_data_list[0])
    print(json.dumps(mapped_data, ensure_ascii=False, indent=2))



if __name__ == "__main__":
    main()

