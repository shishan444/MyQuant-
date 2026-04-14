"""MyQuant API 服务入口"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import uvicorn
    # 直接导入 app 对象
    from api.app import create_app

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
