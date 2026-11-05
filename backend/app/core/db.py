"""数据库引擎 / 会话 / 初始化。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def _sqlite_enable_foreign_keys(dbapi_connection, _record) -> None:
    """SQLite 默认关闭外键，不开启会导致删文件后留下孤儿分析记录。"""
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# PostgreSQL + pgvector 是否真的可用（不可用时自动退回 JSON 向量 + numpy 余弦）
PGVECTOR_READY: bool = False


def get_db() -> Iterator[Session]:
    """FastAPI 依赖注入用的会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """后台任务（非请求上下文）用的会话。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _prepare_postgres() -> bool:
    """尝试启用 pgvector 扩展并建向量列 / 索引。"""
    if not settings.is_postgres:
        return False
    try:
        import pgvector  # noqa: F401
    except Exception:
        return False
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    "ALTER TABLE rag_chunks "
                    "ADD COLUMN IF NOT EXISTS embedding_vec vector"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS rag_chunks_vec_idx "
                    "ON rag_chunks USING hnsw (embedding_vec vector_cosine_ops)"
                )
            )
        return True
    except Exception:
        return False


def init_db() -> None:
    """建表 + 尽可能启用 pgvector 扩展。"""
    global PGVECTOR_READY

    from app import models  # noqa: F401  确保模型已注册

    models.Base.metadata.create_all(bind=engine)
    PGVECTOR_READY = _prepare_postgres()
