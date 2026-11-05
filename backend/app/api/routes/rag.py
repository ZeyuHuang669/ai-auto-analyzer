"""RAG 接口：重建索引、问答、问答历史。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import AnalysisRun, FileAsset, RagChat
from app.schemas import AskRequest
from app.services import pipeline, rag
from app.utils.json import iso_utc, to_python

router = APIRouter(prefix="/api/rag", tags=["RAG 问答"])


@router.post("/index/{file_id}")
def reindex(file_id: str, db: Session = Depends(get_db)):
    asset = db.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(404, "文件不存在")

    run = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.file_id == file_id, AnalysisRun.status == "succeeded")
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )
    if not run:
        try:
            run = pipeline.run_analysis(db, asset, use_ai=False, trigger="index")
        except pipeline.PipelineError as exc:
            raise HTTPException(500, f"分析失败：{exc}") from exc

    df, _ = pipeline.load_frame(asset)
    count = rag.index_dataset(db, asset, df, run.profile, run.analysis, run.charts)
    return {"ok": True, "file_id": file_id, "chunks": count}


@router.post("/ask")
def ask(body: AskRequest, db: Session = Depends(get_db)):
    if body.file_id and not db.get(FileAsset, body.file_id):
        raise HTTPException(404, "指定的文件不存在")
    try:
        return rag.answer(db, body.question, file_id=body.file_id, k=body.k)
    except Exception as exc:
        raise HTTPException(500, f"问答失败：{exc}") from exc


@router.get("/history")
def history(
    file_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Session = Depends(get_db),
):
    query = db.query(RagChat)
    if file_id:
        query = query.filter(RagChat.file_id == file_id)
    chats = query.order_by(RagChat.created_at.desc()).limit(limit).all()
    return to_python(
        [
            {
                "id": c.id,
                "question": c.question,
                "answer": c.answer,
                "sources": c.sources,
                "engine": c.engine,
                "latency_ms": c.latency_ms,
                "created_at": iso_utc(c.created_at),
            }
            for c in chats
        ]
    )


@router.get("/chunks/{file_id}")
def chunks(file_id: str, db: Session = Depends(get_db)):
    rows = db.query(rag.RagChunk).filter(rag.RagChunk.file_id == file_id).all()
    return to_python(
        [{"id": r.id, "kind": r.kind, "title": r.title, "length": len(r.content)} for r in rows]
    )
