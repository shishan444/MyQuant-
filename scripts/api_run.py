#!/usr/bin/env python3
"""MyQuant API 启动脚本"""
import os
import subprocess
import sys
from pathlib import Path

# 设置环境
project_root = Path(__file__).parent.parent
env = os.environ.copy()
env["PYTHONPATH"] = str(project_root)

# 启动 uvicorn
cmd = [
    sys.executable,
    "-m", "uvicorn",
    "api.app:app",
    "--host", "0.0.0.0",
    "--port", "8000",
]

subprocess.run(cmd, env=env, cwd=project_root)
