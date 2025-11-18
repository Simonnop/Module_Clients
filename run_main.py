#!/usr/bin/env python3
"""
单次运行 main 模块的脚本
用法:
    python run_main.py --codes TSLA.US AAPL.US
    python run_main.py --codes TSLA.US AAPL.US  # 批量获取股票数据
"""
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

# 添加 main 目录到 Python 路径
main_dir = Path(__file__).parent / 'main'
sys.path.insert(0, str(main_dir))

# 导入 main 模块
try:
    from main import run
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保 main/main.py 存在")
    sys.exit(1)


def main():
    """
    主函数 - 解析命令行参数并执行
    """
    parser = argparse.ArgumentParser(
        description='单次运行股票实时交易数据获取模块',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_main.py --codes TSLA.US AAPL.US
  python run_main.py --codes TSLA.US AAPL.US USDCNY
        """
    )
    parser.add_argument(
        '--codes', '-c',
        nargs='+',
        required=True,
        help='股票代码列表，例如: --codes TSLA.US AAPL.US'
    )
    
    args = parser.parse_args()
    
    try:
        # 如果没有提供股票代码，显示帮助信息
        if not args.codes:
            parser.print_help()
            print("\n示例: python run_main.py --codes TSLA.US AAPL.US")
            return
        
        # 准备参数
        data = {
            'meta': {
                'timestamp': datetime.now().isoformat(),
                'source': 'run_main_script'
            }
        }
        run_args = {
            'code_list': args.codes
        }
        
        # 执行数据获取
        print(f"\n开始获取 {len(args.codes)} 个股票的实时交易数据: {', '.join(args.codes)}\n")
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


if __name__ == "__main__":
    main()

