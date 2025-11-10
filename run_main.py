#!/usr/bin/env python3
"""
单次运行 main 模块的脚本
用法:
    python run_main.py --codes 159001 159002 159003
    python run_main.py --codes 159001 --status  # 显示License状态
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
    from license_manager import initialize_license_usage, show_license_usage
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保 main/main.py 和 main/license_manager.py 存在")
    sys.exit(1)


def main():
    """
    主函数 - 解析命令行参数并执行
    """
    parser = argparse.ArgumentParser(
        description='单次运行基金数据获取模块',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_main.py --codes 159001 159002 159003
  python run_main.py --codes 159001 --status
  python run_main.py --init  # 初始化License统计
        """
    )
    parser.add_argument(
        '--codes', '-c',
        nargs='+',
        help='基金代码列表，例如: --codes 159001 159002'
    )
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='显示License使用状态'
    )
    parser.add_argument(
        '--init', '-i',
        action='store_true',
        help='初始化License使用统计'
    )
    
    args = parser.parse_args()
    
    try:
        # 初始化License使用统计
        if args.init:
            print("正在初始化License使用统计...")
            try:
                initialize_license_usage()
                print("✓ 初始化完成\n")
            except Exception as e:
                print(f"✗ 初始化失败: {e}\n")
                sys.exit(1)
        
        # 显示License状态
        if args.status:
            print("\nLicense使用状态:")
            show_license_usage()
            return
        
        # 如果没有提供基金代码，显示帮助信息
        if not args.codes:
            parser.print_help()
            print("\n提示: 使用 --status 查看License使用状态")
            print("示例: python run_main.py --codes 159001 159002")
            return
        
        # 初始化License统计（如果尚未初始化）
        try:
            initialize_license_usage()
        except Exception as e:
            print(f"警告: 初始化License使用统计时出现警告: {e}")
        
        # 显示初始License状态
        print("\n开始获取基金数据前，License使用状态:")
        show_license_usage()
        
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
        print(f"\n开始获取 {len(args.codes)} 个基金的数据: {', '.join(args.codes)}\n")
        result = run(data, run_args)
        
        # 显示结果
        print("\n" + "=" * 60)
        print("执行结果:")
        print("=" * 60)
        print(f"状态: {result.get('status', 'unknown')}")
        print(f"总数: {result.get('total', 0)}")
        print(f"成功: {result.get('success_count', 0)}")
        print(f"失败: {result.get('failed_count', 0)}")
        
        if result.get('failed_funds'):
            print(f"失败的基金代码: {', '.join(result['failed_funds'])}")
        
        if result.get('message'):
            print(f"消息: {result['message']}")
        
        print("=" * 60)
        
        # 显示最终License状态
        print("\n获取数据后，License使用状态:")
        show_license_usage()
        
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

