#!/bin/bash
# MyQuant 停止脚本

cd "$(dirname "$0")"

# 加载日志函数库
if [ -f "scripts/lib/logger.sh" ]; then
    source scripts/lib/logger.sh
else
    log_info() { echo "[INFO] $@"; }
fi

log_info "Stopping MyQuant"

# 读取并杀死后端进程
if [ -f .myquant_api.pid ]; then
    API_PID=$(cat .myquant_api.pid)
    if ps -p $API_PID > /dev/null 2>&1; then
        kill $API_PID
        log_info "STOP" "Backend API stopped" "pid=$API_PID"
    fi
    rm -f .myquant_api.pid
fi

# 清理旧的 PID 文件
rm -f .myquant.pid

log_info "STOP" "MyQuant stopped"
echo "MyQuant stopped."
