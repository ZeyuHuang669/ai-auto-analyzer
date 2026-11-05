"""文件管理接口：上传、列表、预览、删除。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import UPLOAD_DIR
from app.core.db import get_db
from app.models import AnalysisRun, FileAsset, RagChunk
from app.serializers import file_dict
from app.services import pipeline, rag, storage
from app.services.loader import SUPPORTED_EXT, load_dataframe
from app.services.profiler import profile_dataframe
from app.utils.json import iso_utc, to_python

router = APIRouter(prefix="/api/files", tags=["文件"])


@router.post("/upload")
def upload_files(
    files: Annotated[list[UploadFile], File(description="CSV / Excel / JSON 文件")],
    sheet: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
):
    """上传一个或多个文件；自动解析、识别字段并预热缓存。"""
    if not files:
        raise HTTPException(400, "没有收到文件")

    created: list[dict] = []
    for upload in files:
        filename = upload.filename or "data.csv"
        try:
            stored_path, sha, size = storage.save_upload(upload.file, filename)
        except storage.StorageError as exc:
            raise HTTPException(400, str(exc)) from exc

        existing = db.query(FileAsset).filter(FileAsset.sha256 == sha).first()
        if existing:
            storage.remove_file(stored_path)
            item = file_dict(existing)
            item["duplicated"] = True
            item["message"] = "相同内容的文件已存在，直接复用"
            created.append(item)
            continue

        asset = FileAsset(
            name=stored_path.name,
            original_name=filename,
            ext=stored_path.suffix.lower(),
            mime=upload.content_type or "",
            size_bytes=size,
            sha256=sha,
            storage_path=str(stored_path),
            status="parsing",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        try:
            result = load_dataframe(stored_path, sheet_name=sheet)
            profile = profile_dataframe(result.df, source_name=asset.name)
            asset.rows = int(result.df.shape[0])
            asset.cols = int(result.df.shape[1])
            asset.columns_meta = profile["columns"]
            asset.sheet_name = result.sheet_name
            asset.sheet_names = result.sheet_names
            asset.status = "ready"
            asset.error = None
            db.commit()
            db.refresh(asset)
            pipeline.prime_cache(asset, result.df, result)

            item = file_dict(asset)
            item["profile_preview"] = {
                "kind": profile["kind"],
                "quality": profile["quality"],
                "summary": profile["summary"],
            }
            item["warnings"] = result.warnings
        except Exception as exc:
            asset.status = "failed"
            asset.error = f"{type(exc).__name__}: {exc}"[:1000]
            db.commit()
            item = file_dict(asset)
            item["error"] = asset.error
            item["message"] = "文件已保存但解析失败"
        created.append(item)

    return {"count": len(created), "files": created}


@router.get("")
def list_files(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(FileAsset)
    if status:
        query = query.filter(FileAsset.status == status)
    total = query.count()
    rows = (
        query.order_by(FileAsset.created_at.desc()).offset(offset).limit(limit).all()
    )

    counts = {
        fid: cnt
        for fid, cnt in db.query(AnalysisRun.file_id, func.count(AnalysisRun.id))
        .group_by(AnalysisRun.file_id)
        .all()
    }
    items = []
    for row in rows:
        item = file_dict(row)
        item["run_count"] = counts.get(row.id, 0)
        items.append(item)
    return {"total": total, "items": items}


@router.get("/{file_id}")
def get_file(file_id: str, db: Session = Depends(get_db)):
    asset = db.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(404, "文件不存在")
    data = file_dict(asset, detail=True)
    data["chunks"] = rag.index_chunk_count(db, file_id)
    data["runs"] = [
        {
            "id": r.id,
            "status": r.status,
            "created_at": iso_utc(r.created_at),
        }
        for r in db.query(AnalysisRun)
        .filter(AnalysisRun.file_id == file_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(10)
    ]
    return data


@router.get("/{file_id}/preview")
def preview_file(
    file_id: str,
    rows: Annotated[int, Query(ge=1, le=500)] = 50,
    db: Session = Depends(get_db),
):
    asset = db.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(404, "文件不存在")
    try:
        df, meta = pipeline.load_frame(asset)
    except Exception as exc:
        raise HTTPException(400, f"读取失败：{exc}") from exc

    head = df.head(rows)
    return to_python(
        {
            "file_id": asset.id,
            "name": asset.name,
            "total_rows": int(df.shape[0]),
            "total_cols": int(df.shape[1]),
            "columns": [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns],
            "rows": head.to_dict(orient="records"),
            "sheet_name": meta.sheet_name,
            "sheet_names": meta.sheet_names,
            "warnings": meta.warnings,
        }
    )


@router.delete("/{file_id}")
def delete_file(file_id: str, db: Session = Depends(get_db)):
    asset = db.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(404, "文件不存在")

    db.query(RagChunk).filter(RagChunk.file_id == file_id).delete()
    # 显式删掉分析记录，不单纯依赖数据库级联（SQLite 旧库可能没开外键）
    db.query(AnalysisRun).filter(AnalysisRun.file_id == file_id).delete()
    path = Path(asset.storage_path)
    db.delete(asset)
    db.commit()

    # 只删我们自己托管的上传副本，不动自动化监视目录里的原始文件
    try:
        if path.is_relative_to(UPLOAD_DIR):
            storage.remove_file(path)
    except (OSError, ValueError):
        pass
    pipeline.invalidate_cache(file_id)
    return {"ok": True, "message": f"已删除 {asset.name}"}


@router.get("/support/formats")
def supported_formats():
    return {"extensions": sorted(SUPPORTED_EXT), "max_upload_mb": 50}
