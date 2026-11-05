"""自动化规则接口。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR, SAMPLE_DIR
from app.core.db import get_db
from app.models import AnalysisRun, AutomationRule, FileAsset
from app.schemas import RuleIn, RuleUpdate
from app.serializers import rule_dict, run_dict
from app.services import automation

router = APIRouter(prefix="/api/automation", tags=["自动化"])


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    rules = db.query(AutomationRule).order_by(AutomationRule.created_at.desc()).all()
    return {"items": [rule_dict(r) for r in rules], "default_dir": str(SAMPLE_DIR)}


@router.post("/rules")
def create_rule(body: RuleIn, db: Session = Depends(get_db)):
    watch = Path(body.watch_dir).expanduser()
    if not watch.is_dir():
        raise HTTPException(400, f"目录不存在：{watch}")
    rule = AutomationRule(
        name=body.name or "新规则",
        watch_dir=str(watch.resolve()),
        pattern=body.pattern or "*",
        enabled=body.enabled,
        use_ai=body.use_ai,
        interval_seconds=body.interval_seconds,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule_dict(rule)


@router.patch("/rules/{rule_id}")
def update_rule(rule_id: str, body: RuleUpdate, db: Session = Depends(get_db)):
    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(404, "规则不存在")
    data = body.model_dump(exclude_unset=True)
    if "watch_dir" in data and data["watch_dir"]:
        watch = Path(data["watch_dir"]).expanduser()
        if not watch.is_dir():
            raise HTTPException(400, f"目录不存在：{watch}")
        data["watch_dir"] = str(watch.resolve())
    for key, value in data.items():
        if value is not None:
            setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule_dict(rule)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(404, "规则不存在")
    db.delete(rule)
    db.commit()
    return {"ok": True, "message": "规则已删除"}


@router.post("/rules/{rule_id}/scan")
async def scan_one(rule_id: str, db: Session = Depends(get_db)):
    rule = db.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(404, "规则不存在")
    result = await asyncio.to_thread(automation.scan_rule, db, rule)
    return result


@router.post("/scan")
async def scan_now():
    results = await asyncio.to_thread(automation.scan_once)
    return {
        "rules": len(results),
        "processed": sum(r["processed"] for r in results),
        "found": sum(r["found"] for r in results),
        "detail": results,
    }


@router.get("/runs")
def automation_runs(limit: int = 20, db: Session = Depends(get_db)):
    runs = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.trigger == "automation")
        .order_by(AnalysisRun.created_at.desc())
        .limit(limit)
        .all()
    )
    names = {
        f.id: f.name for f in db.query(FileAsset).filter(FileAsset.id.in_({r.file_id for r in runs} or {""})).all()
    }
    items = []
    for run in runs:
        item = run_dict(run, names.get(run.file_id, ""), with_content=False)
        item["summary"] = (run.insights or {}).get("summary", "")
        items.append(item)
    return {"items": items, "sample_dir": str(SAMPLE_DIR), "data_dir": str(DATA_DIR)}
