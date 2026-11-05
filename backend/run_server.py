"""PyCharm 直接运行的入口：后端。

在 PyCharm 里右键 Run 这个文件即可启动 FastAPI（等价于
`uvicorn app.main:app --reload --port 8000`）。
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["app"],
    )
