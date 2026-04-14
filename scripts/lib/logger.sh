#!/bin/bash
# MyQuant 日志函数库
# 提供统一的日志格式和日志管理功能

# 日志根目录（相对于项目根目录）
LOG_ROOT="${LOG_ROOT:-$(pwd)/logs}"

# 当前日期
LOG_DATE=$(date +%Y%m%d)

# 日志级别
LEVEL_DEBUG=0
LEVEL_INFO=1
LEVEL_WARN=2
LEVEL_ERROR=3

# 当前日志级别（可通过环境变量 LOG_LEVEL 设置）
CURRENT_LEVEL=${LOG_LEVEL:-$LEVEL_INFO}

# 日志颜色
COLOR_DEBUG='\033[0;36m'    # Cyan
COLOR_INFO='\033[0;32m'     # Green
COLOR_WARN='\033[0;33m'     # Yellow
COLOR_ERROR='\033[0;31m'    # Red
COLOR_RESET='\033[0m'

# 是否启用颜色（在非终端环境中自动禁用）
if [ ! -t 1 ]; then
    COLOR_DEBUG=''
    COLOR_INFO=''
    COLOR_WARN=''
    COLOR_ERROR=''
    COLOR_RESET=''
fi

# 获取日志级别名称
get_level_name() {
    case $1 in
        $LEVEL_DEBUG) echo "DEBUG" ;;
        $LEVEL_INFO)  echo "INFO" ;;
        $LEVEL_WARN)  echo "WARN" ;;
        $LEVEL_ERROR) echo "ERROR" ;;
        *) echo "UNKNOWN" ;;
    esac
}

# 获取日志级别颜色
get_level_color() {
    case $1 in
        $LEVEL_DEBUG) echo "$COLOR_DEBUG" ;;
        $LEVEL_INFO)  echo "$COLOR_INFO" ;;
        $LEVEL_WARN)  echo "$COLOR_WARN" ;;
        $LEVEL_ERROR) echo "$COLOR_ERROR" ;;
        *) echo "" ;;
    esac
}

# 核心日志函数
# 参数: $1=级别 $2=TAG $3=消息 $4=上下文(可选)
_log() {
    local level=$1
    local tag=$2
    local msg=$3
    local context=${4:-""}

    # 检查日志级别
    if [ $level -lt $CURRENT_LEVEL ]; then
        return 0
    fi

    # 时间戳
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # 获取调用者信息（文件名:行号）
    local caller_info=""
    if [ -n "${BASH_SOURCE[2]}" ]; then
        local script_name=$(basename "${BASH_SOURCE[2]}")
        local line_number="${BASH_LINENO[1]}"
        caller_info="$script_name:$line_number"
    fi

    # 构建日志消息
    local level_name=$(get_level_name $level)
    local color=$(get_level_color $level)
    local log_msg="[$timestamp] [$tag] [$level_name] $msg"

    # 添加上下文
    if [ -n "$context" ]; then
        log_msg="$log_msg | $context"
    fi

    # 添加源码位置
    if [ -n "$caller_info" ]; then
        log_msg="$log_msg | $caller_info"
    fi

    # 输出到控制台（带颜色）
    if [ -n "$color" ]; then
        echo -e "${color}${log_msg}${COLOR_RESET}"
    else
        echo "$log_msg"
    fi

    # 同时输出到日志文件（不带颜色）
    _log_to_file "$log_msg"
}

# 写入日志文件
# 参数: $1=日志消息
_log_to_file() {
    local msg=$1
    local log_file="$LOG_ROOT/start/start_$LOG_DATE.log"

    # 确保日志目录存在
    mkdir -p "$(dirname "$log_file")"

    # 写入日志文件
    echo "$msg" >> "$log_file"
}

# 公共日志函数
log_debug() {
    _log $LEVEL_DEBUG "$@"
}

log_info() {
    _log $LEVEL_INFO "$@"
}

log_warn() {
    _log $LEVEL_WARN "$@"
}

log_error() {
    _log $LEVEL_ERROR "$@"
}

# 启动专用日志函数（带特殊标记）
log_start() {
    local msg=$1
    local context=${2:-""}
    _log $LEVEL_INFO "START" "$msg" "$context"
}

# 初始化日志目录
init_log_dir() {
    local log_root="${1:-$LOG_ROOT}"

    mkdir -p "$log_root/start"
    mkdir -p "$log_root/api"
    mkdir -p "$log_root/web"
    mkdir -p "$log_root/archive"

    log_info "SYSTEM" "log directories initialized" "path=$log_root"
}

# 日志轮转（按日期）
rotate_log() {
    local log_file=$1
    local max_size_mb=${2:-100}  # 默认100MB

    if [ ! -f "$log_file" ]; then
        return 0
    fi

    # 获取文件大小（MB）
    local size_mb=$(du -m "$log_file" | cut -f1)

    # 如果超过最大大小，进行切分
    if [ $size_mb -ge $max_size_mb ]; then
        local counter=1
        local rotated_file="${log_file%.*}_$counter.log"

        # 找到可用的序号
        while [ -f "$rotated_file" ]; do
            counter=$((counter + 1))
            rotated_file="${log_file%.*}_$counter.log"
        done

        mv "$log_file" "$rotated_file"
        log_info "SYSTEM" "log rotated" "from=$log_file to=$rotated_file"
    fi
}

# 清理过期日志
cleanup_logs() {
    local days=${1:-7}  # 默认保留7天
    local cutoff_date=$(date -d "$days days ago" +%Y%m%d 2>/dev/null || date -v-${days}d +%Y%m%d)

    log_info "SYSTEM" "cleaning old logs" "before=$cutoff_date, keep_days=$days"

    # 清理各目录中的过期日志
    for dir in start api web; do
        if [ -d "$LOG_ROOT/$dir" ]; then
            find "$LOG_ROOT/$dir" -name "*.log" -type f | while read log_file; do
                local file_date=$(basename "$log_file" | grep -oE '[0-9]{8}')
                if [ -n "$file_date" ] && [ "$file_date" -lt "$cutoff_date" ]; then
                    rm -f "$log_file"
                    log_info "SYSTEM" "old log deleted" "file=$log_file"
                fi
            done
        fi
    done

    # 归档30天前的日志到archive目录
    local archive_cutoff=$(date -d "30 days ago" +%Y%m%d 2>/dev/null || date -v-30d +%Y%m%d)
    for dir in start api web; do
        if [ -d "$LOG_ROOT/$dir" ]; then
            find "$LOG_ROOT/$dir" -name "*.log" -type f | while read log_file; do
                local file_date=$(basename "$log_file" | grep -oE '[0-9]{8}')
                if [ -n "$file_date" ] && [ "$file_date" -lt "$archive_cutoff" ]; then
                    local archive_dir="$LOG_ROOT/archive/${file_date:0:4}-${file_date:4:2}"
                    mkdir -p "$archive_dir"
                    mv "$log_file" "$archive_dir/"
                    log_info "SYSTEM" "log archived" "file=$log_file to=$archive_dir"
                fi
            done
        fi
    done
}

# 获取今天的日志文件路径
get_log_file() {
    local type=$1  # start, api, web
    local module=${2:-"start"}

    echo "$LOG_ROOT/$module/${type}_$LOG_DATE.log"
}

# 导出函数以便其他脚本使用
export -f log_debug log_info log_warn log_error log_start
export -f init_log_dir rotate_log cleanup_logs get_log_file
