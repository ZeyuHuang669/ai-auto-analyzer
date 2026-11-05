"""系统状态接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import db as db_module
from app.core.config import DATA_DIR, UPLOAD_DIR, get_settings
from app.core.db import get_db
from app.models import AnalysisRun, AutomationRule, FileAsset, RagChat, RagChunk
from app.services.embeddings import get_embedder
from app.services.llm import get_llm
from app.services.loader import SUPPORTED_EXT
from app.utils.json import iso_utc, to_python

router = APIRouter(prefix="/api", tags=["系统"])
settings = get_settings()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.query(func.count(FileAsset.id)).scalar()
    except Exception:
        db_ok = False
    llm = get_llm()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "database_url": "postgresql" if settings.is_postgres else "sqlite",
        "vector_mode": "pgvector" if db_module.PGVECTOR_READY else "numpy-cosine",
        "embedding": get_embedder().active,
        "ai_enabled": bool(settings.openai_api_key),
        "ai_available": llm.available,
        "model": llm.model,
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    file_rows = db.query(func.count(FileAsset.id), func.coalesce(func.sum(FileAsset.rows), 0)).one()
    run_counts = dict(
        db.query(AnalysisRun.status, func.count(AnalysisRun.id))
        .group_by(AnalysisRun.status)
        .all()
    )
    total_runs = sum(run_counts.values())
    chunks = db.query(func.count(RagChunk.id)).scalar() or 0
    chats = db.query(func.count(RagChat.id)).scalar() or 0
    rules = db.query(func.count(AutomationRule.id)).scalar() or 0
    enabled_rules = (
        db.query(func.count(AutomationRule.id))
        .filter(AutomationRule.enabled.is_(True))
        .scalar()
        or 0
    )

    storage_bytes = 0
    for path in UPLOAD_DIR.rglob("*"):
        if path.is_file():
            storage_bytes += path.stat().st_size

    recent = (
        db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(5).all()
    )
    names = {
        f.id: f.name for f in db.query(FileAsset).filter(FileAsset.id.in_({r.file_id for r in recent} or {""})).all()
    }

    return to_python(
        {
            "files": {"total": file_rows[0], "rows": int(file_rows[1] or 0)},
            "runs": {"total": total_runs, "by_status": run_counts},
            "rag": {"chunks": chunks, "chats": chats},
            "automation": {"rules": rules, "enabled": enabled_rules},
            "storage": {
                "bytes": storage_bytes,
                "mb": round(storage_bytes / 1024 / 1024, 2),
                "path": str(DATA_DIR),
            },
            "ai": {
                "enabled": bool(settings.openai_api_key),
                "model": settings.llm_model,
                "vector_mode": "pgvector" if db_module.PGVECTOR_READY else "numpy-cosine",
            },
            "recent_runs": [
                {
                    "id": r.id,
                    "file_id": r.file_id,
                    "file_name": names.get(r.file_id, ""),
                    "status": r.status,
                    "trigger": r.trigger,
                    "created_at": iso_utc(r.created_at),
                    "summary": (r.insights or {}).get("summary", ""),
                    "charts_count": len(r.charts or []),
                    "duration_ms": r.duration_ms,
                }
                for r in recent
            ],
        }
    )


@router.get("/config")
def config():
    return {
        "app_name": settings.app_name,
        "model": settings.llm_model,
        "ai_enabled": bool(settings.openai_api_key),
        "embedding_model": settings.embedding_model or "本地哈希向量",
        "vector_mode": "pgvector" if db_module.PGVECTOR_READY else "numpy-cosine",
        "database": "postgresql" if settings.is_postgres else "sqlite",
        "max_upload_mb": settings.max_upload_mb,
        "supported_formats": sorted(SUPPORTED_EXT),
    }
