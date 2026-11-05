"""自动分析接口：触发流水线、查看历史、导出报告。"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import AnalysisRun, FileAsset
from app.schemas import RunRequest
from app.serializers import run_dict
from app.services import pipeline

router = APIRouter(prefix="/api/analysis", tags=["数据分析"])


def _run_or_404(db: Session, run_id: str) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if not run:
        raise HTTPException(404, "分析记录不存在")
    return run


@router.post("/{file_id}/run")
def run_on_file(
    file_id: str,
    use_ai: Annotated[bool, Query(description="是否调用大模型生成结论")] = True,
    force: Annotated[bool, Query(description="强制重新分析")] = False,
    trigger: Annotated[str, Query()] = "manual",
    db: Session = Depends(get_db),
):
    asset = db.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(404, "文件不存在")
    if asset.status == "failed":
        raise HTTPException(400, f"文件解析失败：{asset.error or '未知原因'}")

    try:
        run = pipeline.run_analysis(
            db, asset, use_ai=use_ai, trigger=trigger, force=force
        )
    except pipeline.PipelineError as exc:
        raise HTTPException(500, f"分析失败：{exc}") from exc
    return pipeline.run_payload(run, asset)


@router.post("/run")
def run_by_body(body: RunRequest, db: Session = Depends(get_db)):
    asset = db.get(FileAsset, body.file_id)
    if not asset:
        raise HTTPException(404, "文件不存在")
    try:
        run = pipeline.run_analysis(
            db, asset, use_ai=body.use_ai, trigger="api", force=body.force
        )
    except pipeline.PipelineError as exc:
        raise HTTPException(500, f"分析失败：{exc}") from exc
    return pipeline.run_payload(run, asset)


@router.get("/runs")
def list_runs(
    file_id: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
):
    query = db.query(AnalysisRun)
    if file_id:
        query = query.filter(AnalysisRun.file_id == file_id)
    if status:
        query = query.filter(AnalysisRun.status == status)
    total = query.count()
    runs = query.order_by(AnalysisRun.created_at.desc()).offset(offset).limit(limit).all()

    file_names = {
        f.id: f.name
        for f in db.query(FileAsset)
        .filter(FileAsset.id.in_({r.file_id for r in runs} or {""}))
        .all()
    }
    items = []
    for run in runs:
        item = run_dict(run, file_names.get(run.file_id, ""), with_content=False)
        insights = run.insights or {}
        item["summary"] = insights.get("summary", "")
        item["charts_count"] = len(run.charts or [])
        item["findings_count"] = len((run.analysis or {}).get("findings", []))
        item["rows"] = (run.profile or {}).get("rows", 0)
        items.append(item)
    return {"total": total, "items": items}


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = _run_or_404(db, run_id)
    return run_dict(run)


@router.get("/runs/{run_id}/export")
def export_run(run_id: str, db: Session = Depends(get_db)):
    run = _run_or_404(db, run_id)
    payload = run_dict(run)
    filename = f"analysis-{(run.file.name if run.file else run_id)}.json"
    return JSONResponse(
        content=json.loads(json.dumps(payload, ensure_ascii=False)),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/runs/{run_id}")
def delete_run(run_id: str, db: Session = Depends(get_db)):
    run = _run_or_404(db, run_id)
    db.delete(run)
    db.commit()
    return {"ok": True, "message": "已删除该条分析记录"}
