"""全局配置：从项目根目录的 .env 读取。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] 是项目根目录（PythonProject1）
PROJECT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
SAMPLE_DIR = DATA_DIR / "samples"
REPORT_DIR = DATA_DIR / "reports"

for _d in (DATA_DIR, UPLOAD_DIR, SAMPLE_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AI 自动化文件处理系统"

    # 数据库：默认 SQLite，方便开箱即用；改成 postgresql+psycopg://... 即启用 pgvector
    database_url: str = Field(
        default=f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}",
        description="SQLAlchemy 连接串",
    )

    # AI 模型（OpenAI 兼容协议）
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout: float = 60.0
    llm_max_retries: int = 1
    use_ai_insights: bool = True

    # 向量检索
    embedding_model: str = ""  # 留空则使用本地哈希向量，无需联网
    embedding_dim: int = 512

    # 上传限制
    max_upload_mb: int = 50
    preview_rows: int = 100
    max_chart_points: int = 800

    # 自动化扫描间隔（秒）
    automation_interval_seconds: int = 60

    cors_origins: list[str] = ["*"]

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
