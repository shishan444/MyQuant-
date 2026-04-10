#!/usr/bin/env bash
# MyQuant 应用启动脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$APP_DIR/venv/bin/python3"
PID_FILE="$APP_DIR/.myquant.pid"
LOG_FILE="$APP_DIR/logs/app.log"
HOST="${MYQUANT_HOST:-0.0.0.0}"
PORT="${MYQUANT_PORT:-8501}"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 检查虚拟环境
check_venv() {
    if [[ ! -x "$VENV_PYTHON" ]]; then
        error "虚拟环境不存在: $VENV_PYTHON"
        echo "请先执行: python3 -m venv $APP_DIR/venv && source $APP_DIR/venv/bin/activate && pip install -r $APP_DIR/requirements.txt"
        exit 1
    fi
}

# 检查是否已在运行
check_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(<"$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            warn "MyQuant 已在运行 (PID: $pid, 端口: $PORT)"
            exit 0
        else
            warn "发现残留 PID 文件，清理中..."
            rm -f "$PID_FILE"
        fi
    fi
}

# 创建日志目录
ensure_dirs() {
    mkdir -p "$APP_DIR/logs"
}

# 启动应用
start() {
    check_venv
    check_running
    ensure_dirs

    info "启动 MyQuant 应用..."
    info "  主机: $HOST"
    info "  端口: $PORT"
    info "  日志: $LOG_FILE"

    cd "$APP_DIR"
    nohup "$VENV_PYTHON" -m streamlit run main.py \
        --server.headless=true \
        --server.address="$HOST" \
        --server.port="$PORT" \
        >> "$LOG_FILE" 2>&1 &

    local pid=$!
    echo "$pid" > "$PID_FILE"

    # 等待启动
    local retries=10
    while ((retries-- > 0)); do
        if curl -s -o /dev/null "http://localhost:$PORT/_stcore/health" 2>/dev/null; then
            info "MyQuant 启动成功 (PID: $pid)"
            info "访问地址: http://localhost:$PORT"
            exit 0
        fi
        sleep 1
    done

    # 检查进程是否还活着
    if kill -0 "$pid" 2>/dev/null; then
        info "MyQuant 进程已启动 (PID: $pid)，但健康检查未通过，请查看日志:"
        info "  tail -f $LOG_FILE"
    else
        error "MyQuant 启动失败，请查看日志:"
        error "  cat $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

start
