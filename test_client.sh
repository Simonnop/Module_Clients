#!/bin/bash

# template 模块启动脚本

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
if ! python3 -c "import websocket" 2>/dev/null; then
    echo "警告: 检测到缺少依赖包，请先运行: pip install -r requirements.txt"
fi

# 检查 module_hash.txt 是否存在
if [ ! -f "config/module_hash.txt" ]; then
    echo "错误: 未找到 config/module_hash.txt 文件"
    echo "请先运行 connect/register.py 进行模块注册"
    exit 1
fi

# 启动客户端连接
echo "正在启动模块..."
python3 connect/client_connect.py

