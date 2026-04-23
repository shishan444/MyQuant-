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

# 读取并杀死前端进程
if [ -f .myquant_web.pid ]; then
    WEB_PID=$(cat .myquant_web.pid)
    if ps -p $WEB_PID > /dev/null 2>&1; then
        kill $WEB_PID 2>/dev/null
        # 子进程可能还在，给一点时间
        sleep 1
        kill -9 $WEB_PID 2>/dev/null
        log_info "STOP" "Frontend dev server stopped" "pid=$WEB_PID"
    fi
    rm -f .myquant_web.pid
fi

# 清理旧的 PID 文件
rm -f .myquant.pid

log_info "STOP" "MyQuant stopped"
echo "MyQuant stopped."
