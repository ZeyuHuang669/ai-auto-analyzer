"""AI Planner 接口：自然语言 → 分析动作。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas import PlannerRequest
from app.services import planner

router = APIRouter(prefix="/api/planner", tags=["AI Planner"])


@router.post("/run")
def run(body: PlannerRequest, db: Session = Depends(get_db)):
    try:
        return planner.run_planner(db, body.question, body.file_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"规划执行失败：{exc}") from exc


@router.get("/intents")
def intents():
    return {
        "intents": [
            {"key": "trend", "label": "趋势分析", "example": "销售额最近几个月的趋势如何？"},
            {"key": "rank", "label": "排名对比", "example": "各个地区销售额排名"},
            {"key": "distribution", "label": "分布形态", "example": "订单金额的分布集中在什么区间？"},
            {"key": "correlation", "label": "相关性", "example": "客单价和销量有关系吗？"},
            {"key": "missing", "label": "缺失检查", "example": "哪些字段缺失比较多？"},
            {"key": "summary", "label": "整体概览", "example": "帮我整体介绍一下这份数据"},
        ]
    }
