#!/usr/bin/env python3
"""
单次运行 main 模块的脚本（仅 RSI 监控）
用法:
    python run_main.py --items '{"items":[{"code":"SH600900","name":"长江电力","rsi_high":70,"rsi_low":30,"emails":["a@qq.com","b@qq.com"]}]}'
"""
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# 添加 main 目录到 Python 路径
main_dir = Path(__file__).parent / 'main'
sys.path.insert(0, str(main_dir))

DEFAULT_RSI_ITEMS = {
    "items": [
        {
            "code": "SH600900",
            "name": "长江电力",
            "rsi_high": 70,
            "rsi_low": 30,
            "emails": [
                "741617293@qq.com"
            ]
        }
    ]
}

# 导入 main 模块
try:
    from main import run, close_mongo_connection
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保 main/main.py 存在")
    sys.exit(1)


def main():
    """
    主函数 - 解析命令行参数并执行
    """
    parser = argparse.ArgumentParser(
        description='单次运行 RSI 监控模块',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_main.py --items '{"items":[{"code":"SH600900","name":"长江电力","rsi_high":70,"rsi_low":30,"emails":["741617293@qq.com"]}]}'"""
    )
    default_items_json = json.dumps(DEFAULT_RSI_ITEMS, ensure_ascii=False)
    parser.add_argument(
        '--items', '-i',
        default=default_items_json,
        help='RSI 监控参数 JSON 字符串，例如: --items \'{"items":[...]}\'. 默认使用内置示例'
    )
    
    args = parser.parse_args()
    
    try:
        # 准备参数
        data = {
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'source': 'run_main_script'
            }
        }
        try:
            parsed = json.loads(args.items)
        except json.JSONDecodeError as exc:
            print(f"解析 items 参数失败: {exc}")
            sys.exit(1)

        run_args = parsed
        
        # 执行数据获取
        print("\n开始执行 RSI 监控\n")
        result = run(data, run_args)

        # 显示结果
        print("\n" + "=" * 60)
        print("执行结果:")
        print("=" * 60)
        print(f"状态: {result.get('status', 'unknown')}")
        print(f"总数: {result.get('total', 0)}")
        print(f"成功: {result.get('success_count', 0)}")
        print(f"失败: {result.get('failed_count', 0)}")

        if result.get('failed_stocks'):
            print(f"失败的股票代码: {', '.join(result['failed_stocks'])}")

        if result.get('message'):
            print(f"消息: {result['message']}")

        print("=" * 60)

        # 根据结果设置退出码
        if result.get('status') == 'error' or result.get('failed_count', 0) > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        close_mongo_connection()


if __name__ == "__main__":
    main()

