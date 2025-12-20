#!/usr/bin/env python3
"""
单次运行 main 调度器脚本（从 MongoDB 读取 stock_watch，支持多策略）
用法示例:
    python run_main.py --signal rsi
"""
import sys
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

# 将项目根目录加入路径，便于导入 main 包
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

try:
    from main import main as entry
    from main import common as common_lib
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保 main 包可用")
    sys.exit(1)

# 脚本级日志（策略内部仍使用 common 的配置）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def format_signal_result(signal: str, result: dict) -> str:
    """格式化单个策略执行结果"""
    lines = [
        f"信号: {signal}",
        f"状态: {result.get('status', 'unknown')}",
    ]
    if result.get('message'):
        lines.append(f"消息: {result.get('message')}")
    if result.get('errors'):
        lines.append(f"错误: {result.get('errors')}")
    items = result.get('items') or []
    lines.append(f"标的数量: {len(items)}")
    return "\n".join(lines)


def main():
    """解析命令行并执行调度"""
    parser = argparse.ArgumentParser(description='运行多策略监控（从 stock_watch 拉取）')
    parser.add_argument('--signal', '-s', help='仅运行指定信号，如 rsi 或 ma_cross', default=None)
    args = parser.parse_args()

    run_args = {}
    if args.signal:
        run_args['signal'] = args.signal

    data = {
        'meta': {
            'timestamp': datetime.now().isoformat(),
            'source': 'run_main_script'
        }
    }

    try:
        logger.info("开始执行监控调度")
        result = entry.run(data, run_args)

        print("\n" + "=" * 60)
        print("执行结果")
        print("=" * 60)
        print(f"总体状态: {result.get('status', 'unknown')}")
        print(f"执行信号: {', '.join(result.get('executed_signals', []))}")
        if result.get('errors'):
            print(f"调度错误: {result['errors']}")

        print("-" * 60)
        for signal, res in (result.get('results') or {}).items():
            print(format_signal_result(signal, res))
            print("-" * 60)

        exit_err = result.get('status') == 'error' or bool(result.get('errors'))
        sys.exit(1 if exit_err else 0)
    except KeyboardInterrupt:
        print("\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        common_lib.close_mongo_connection()


if __name__ == "__main__":
    main()
