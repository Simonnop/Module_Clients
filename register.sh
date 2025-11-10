#!/bin/bash

# 模块注册脚本

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REGISTER_SCRIPT="$SCRIPT_DIR/connect/register.py"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 检查 Python 环境
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "未找到 python3，请先安装 Python 3"
        exit 1
    fi
}

# 检查注册脚本是否存在
check_register_script() {
    if [ ! -f "$REGISTER_SCRIPT" ]; then
        print_error "未找到 register.py 文件: $REGISTER_SCRIPT"
        exit 1
    fi
}

# 检查配置文件是否存在
check_config() {
    if [ ! -f "$SCRIPT_DIR/config/.env" ]; then
        print_warning "未找到 config/.env 文件"
        if [ -f "$SCRIPT_DIR/config/.env.example" ]; then
            print_info "请先复制示例配置文件:"
            echo "  cp config/.env.example config/.env"
            echo "然后编辑 config/.env 文件，填入实际配置值"
        else
            print_error "请先创建 config/.env 文件并配置服务器地址和端口"
        fi
        exit 1
    fi
}

# 主函数
main() {
    print_info "开始注册模块..."
    
    # 检查环境
    check_python
    check_register_script
    check_config
    
    # 执行注册
    print_info "正在连接服务器并注册模块..."
    python3 "$REGISTER_SCRIPT"
    
    if [ $? -eq 0 ]; then
        print_info "模块注册完成"
        
        # 检查是否生成了 hash 文件
        if [ -f "$SCRIPT_DIR/config/module_hash.txt" ]; then
            print_info "模块哈希值已保存到 config/module_hash.txt"
            echo ""
            print_info "可以使用以下命令启动模块:"
            echo "  ./manage.sh start"
        else
            print_warning "未找到模块哈希文件，注册可能未完全成功"
        fi
        exit 0
    else
        print_error "模块注册失败，请检查错误信息"
        exit 1
    fi
}

main "$@"

