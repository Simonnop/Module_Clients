#!/bin/bash

# 模块注册脚本

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 切换到脚本目录
cd "$SCRIPT_DIR"

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    exit 1
fi

# 检查是否已安装依赖
if ! python3 -c "import requests" 2>/dev/null; then
    echo "错误: 缺少依赖包 requests，请先运行: pip install -r requirements.txt"
    exit 1
fi

# 检查 .env 文件是否存在
if [ ! -f "config/.env" ]; then
    echo "警告: 未找到 config/.env 文件"
    echo "请先创建 config/.env 文件并配置 SERVER_IP 和 SERVER_PORT"
    echo ""
    echo "如果存在 config/.env.example，可以复制它："
    echo "  cp config/.env.example config/.env"
    echo ""
    read -p "是否继续注册？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 执行注册
echo "=========================================="
echo "开始注册模块..."
echo "=========================================="
echo ""

python3 connect/register.py

# 检查注册结果
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "注册完成！"
    echo "=========================================="
    
    # 检查 module_hash.txt 是否已创建
    if [ -f "config/module_hash.txt" ]; then
        echo ""
        echo "模块哈希值已保存到: config/module_hash.txt"
        echo "哈希值内容:"
        cat config/module_hash.txt
    fi
else
    echo ""
    echo "=========================================="
    echo "注册失败，请检查错误信息"
    echo "=========================================="
    exit 1
fi

