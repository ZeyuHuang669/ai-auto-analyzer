"""PyCharm 直接运行的入口：前端。

在 PyCharm 里右键 Run 这个文件即可启动 Streamlit（等价于
`streamlit run app.py`），默认地址 http://localhost:8501。
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(HERE / "app.py"),
            "--server.port",
            "8501",
        ],
        cwd=str(HERE),
        check=False,
    )
