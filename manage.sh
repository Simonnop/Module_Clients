#!/bin/bash

# 模块管理脚本

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MODULE_NAME="client"
PID_FILE="$SCRIPT_DIR/.${MODULE_NAME}.pid"
LOG_DIR="$SCRIPT_DIR/logs"
MAIN_SCRIPT="$SCRIPT_DIR/connect/client_connect.py"

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

# 检查依赖
check_dependencies() {
    if ! python3 -c "import websocket" 2>/dev/null; then
        print_warning "检测到缺少依赖包"
        return 1
    fi
    return 0
}

# 检查模块注册
check_registration() {
    if [ ! -f "$SCRIPT_DIR/config/module_hash.txt" ]; then
        print_error "未找到 config/module_hash.txt 文件"
        print_info "请先运行: $0 register"
        return 1
    fi
    return 0
}

# 获取进程 PID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "$PID"
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# 启动模块
start() {
    check_python
    
    if get_pid > /dev/null; then
        PID=$(get_pid)
        print_warning "模块已在运行中 (PID: $PID)"
        return 1
    fi
    
    if ! check_registration; then
        return 1
    fi
    
    if ! check_dependencies; then
        print_info "正在安装依赖..."
        install_deps
    fi
    
    print_info "正在启动 $MODULE_NAME 模块..."
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    # 后台启动并保存 PID
    nohup python3 "$MAIN_SCRIPT" > "$LOG_DIR/startup.log" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    # 等待一下确认启动成功
    sleep 1
    if ps -p "$PID" > /dev/null 2>&1; then
        print_info "模块启动成功 (PID: $PID)"
        print_info "日志文件: $LOG_DIR/startup.log"
        return 0
    else
        rm -f "$PID_FILE"
        print_error "模块启动失败，请查看日志: $LOG_DIR/startup.log"
        return 1
    fi
}

# 停止模块
stop() {
    if ! get_pid > /dev/null; then
        print_warning "模块未运行"
        return 1
    fi
    
    PID=$(get_pid)
    print_info "正在停止 $MODULE_NAME 模块 (PID: $PID)..."
    
    kill "$PID" 2>/dev/null
    
    # 等待进程结束
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            print_info "模块已停止"
            return 0
        fi
        sleep 1
    done
    
    # 如果还没停止，强制杀死
    if ps -p "$PID" > /dev/null 2>&1; then
        print_warning "强制停止进程..."
        kill -9 "$PID" 2>/dev/null
        sleep 1
        rm -f "$PID_FILE"
        print_info "模块已强制停止"
    fi
    
    return 0
}

# 重启模块
restart() {
    print_info "正在重启 $MODULE_NAME 模块..."
    stop
    sleep 2
    start
}

# 查看状态
status() {
    if get_pid > /dev/null; then
        PID=$(get_pid)
        print_info "模块运行中 (PID: $PID)"
        
        # 显示进程信息
        ps -p "$PID" -o pid,ppid,cmd,etime,stat 2>/dev/null
        
        return 0
    else
        print_warning "模块未运行"
        return 1
    fi
}

# 查看日志
logs() {
    local lines=${1:-50}
    
    if [ -d "$LOG_DIR" ]; then
        # 查找最新的日志文件
        local latest_log=$(find "$LOG_DIR" -name "*.log" -type f -exec stat -f "%m %N" {} \; 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
        # macOS 兼容性：如果上面的命令失败，使用 ls 命令
        if [ -z "$latest_log" ]; then
            latest_log=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)
        fi
        
        if [ -n "$latest_log" ] && [ -f "$latest_log" ]; then
            print_info "显示最新日志 (最后 $lines 行):"
            echo "---"
            tail -n "$lines" "$latest_log"
        else
            print_warning "未找到日志文件"
        fi
        
        # 显示启动日志
        if [ -f "$LOG_DIR/startup.log" ]; then
            echo ""
            print_info "启动日志:"
            echo "---"
            tail -n "$lines" "$LOG_DIR/startup.log"
        fi
    else
        print_warning "日志目录不存在"
    fi
}

# 实时查看日志
logs_follow() {
    if [ -d "$LOG_DIR" ]; then
        local latest_log=$(find "$LOG_DIR" -name "*.log" -type f -exec stat -f "%m %N" {} \; 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
        # macOS 兼容性：如果上面的命令失败，使用 ls 命令
        if [ -z "$latest_log" ]; then
            latest_log=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)
        fi
        
        if [ -n "$latest_log" ] && [ -f "$latest_log" ]; then
            print_info "实时查看日志 (Ctrl+C 退出):"
            tail -f "$latest_log"
        else
            print_warning "未找到日志文件"
        fi
    else
        print_warning "日志目录不存在"
    fi
}

# 安装依赖
install_deps() {
    check_python
    
    if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
        print_error "未找到 requirements.txt 文件"
        return 1
    fi
    
    print_info "正在安装依赖包..."
    pip3 install -r "$SCRIPT_DIR/requirements.txt"
    
    if [ $? -eq 0 ]; then
        print_info "依赖安装完成"
        return 0
    else
        print_error "依赖安装失败"
        return 1
    fi
}

# 注册模块
register() {
    check_python
    
    local register_script="$SCRIPT_DIR/connect/register.py"
    
    if [ ! -f "$register_script" ]; then
        print_error "未找到 register.py 文件"
        return 1
    fi
    
    print_info "正在注册模块..."
    python3 "$register_script"
    
    if [ $? -eq 0 ]; then
        print_info "模块注册完成"
        return 0
    else
        print_error "模块注册失败"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    echo "用法: $0 {start|stop|restart|status|logs|logs-follow|install|register|help}"
    echo ""
    echo "命令:"
    echo "  start        启动模块（后台运行）"
    echo "  stop         停止模块"
    echo "  restart      重启模块"
    echo "  status       查看运行状态"
    echo "  logs [N]     查看日志（默认最后50行）"
    echo "  logs-follow  实时查看日志"
    echo "  install      安装依赖包"
    echo "  register     注册模块"
    echo "  help         显示帮助信息"
    echo ""
}

# 主函数
main() {
    case "${1:-help}" in
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        status)
            status
            ;;
        logs)
            logs "${2:-50}"
            ;;
        logs-follow|follow)
            logs_follow
            ;;
        install)
            install_deps
            ;;
        register)
            register
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"

