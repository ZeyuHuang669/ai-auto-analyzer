"""ORM 模型：文件、分析记录、RAG 片段、问答、自动化规则。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class FileAsset(Base):
    """上传的文件。"""

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(512))
    original_name: Mapped[str] = mapped_column(String(512))
    ext: Mapped[str] = mapped_column(String(16), default="")
    mime: Mapped[str] = mapped_column(String(128), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), index=True, default="")
    storage_path: Mapped[str] = mapped_column(Text, default="")
    sheet_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sheet_names: Mapped[list] = mapped_column(JSON, default=list)
    rows: Mapped[int] = mapped_column(Integer, default=0)
    cols: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    columns_meta: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="file", cascade="all, delete-orphan", passive_deletes=True
    )


class AnalysisRun(Base):
    """一次完整的自动分析结果（识别 → 分析 → 选图 → 出图 → 结论）。"""

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("files.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="pending")
    trigger: Mapped[str] = mapped_column(String(24), default="manual")  # manual / automation / api
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    charts: Mapped[list] = mapped_column(JSON, default=list)
    insights: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(96), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    file: Mapped[FileAsset] = relationship(back_populates="runs")


class RagChunk(Base):
    """RAG 检索片段；embedding 以 JSON 文本存储，Postgres 下另有 pgvector 列。"""

    __tablename__ = "rag_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(String(32), index=True)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="dataset")
    title: Mapped[str] = mapped_column(String(256), default="")
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[str] = mapped_column(Text, default="[]")
    dim: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RagChat(Base):
    """问答历史。"""

    __tablename__ = "rag_chats"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    file_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    engine: Mapped[str] = mapped_column(String(24), default="local")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AutomationRule(Base):
    """自动化规则：监视目录里的新文件并自动跑分析。"""

    __tablename__ = "automation_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), default="新规则")
    watch_dir: Mapped[str] = mapped_column(Text)
    pattern: Mapped[str] = mapped_column(String(64), default="*.csv")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    use_ai: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
