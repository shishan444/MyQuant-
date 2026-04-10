#!/usr/bin/env bash
# MyQuant 应用停止脚本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$APP_DIR/.myquant.pid"
PORT="${MYQUANT_PORT:-8501}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

stop_by_pid() {
    if [[ ! -f "$PID_FILE" ]]; then
        return 1
    fi
    local pid
    pid=$(<"$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        info "停止 MyQuant (PID: $pid)..."
        kill "$pid"
        local retries=10
        while ((retries-- > 0)) && kill -0 "$pid" 2>/dev/null; do
            sleep 1
        done
        if kill -0 "$pid" 2>/dev/null; then
            warn "进程未响应，强制终止..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
        info "已停止"
        return 0
    else
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_by_port() {
    local pids
    pids=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [[ -z "$pids" ]]; then
        return 1
    fi
    info "通过端口 $PORT 发现进程: $pids"
    for pid in $pids; do
        info "停止进程 $pid..."
        kill "$pid" 2>/dev/null || true
    done
    sleep 2
    # 清理残留
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    info "已停止"
    return 0
}

# 主流程
if stop_by_pid; then
    exit 0
fi

if stop_by_port; then
    exit 0
fi

warn "MyQuant 未在运行"
