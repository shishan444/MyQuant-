#!/bin/bash
# MyQuant API 启动脚本
cd "$(dirname "$0")"

# 加载日志函数库
if [ -f "scripts/lib/logger.sh" ]; then
    source scripts/lib/logger.sh
else
    log_info() { echo "[INFO] $@"; }
    log_error() { echo "[ERROR] $@"; }
fi

# MyQuant 模块的父目录需要在 PYTHONPATH 中
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 设置日志级别（可通过环境变量覆盖）
export LOG_LEVEL=${LOG_LEVEL:-1}  # 1=INFO

log_start "Starting API Server" "port=8000"

# 启动 uvicorn，同时输出到控制台和日志文件
exec venv/bin/python -m uvicorn api.app:app --host 0.0.0.0 --port 8000
