"""分析流水线：读取 → 识别 → 分析 → 选图 → 画图 → 结论 → 落库 (+ 建索引)。"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models import AnalysisRun, FileAsset
from app.services.analysis import analyze_dataframe
from app.services.charts import recommend_charts
from app.services.insights import generate_insights
from app.services.loader import LoadResult, load_dataframe
from app.services.profiler import profile_dataframe
from app.services import rag
from app.utils.json import iso_utc, to_python

_CACHE: "OrderedDict[str, tuple[float, pd.DataFrame, LoadResult]]" = OrderedDict()
_CACHE_MAX = 6


class PipelineError(RuntimeError):
    pass


def _cache_key(file: FileAsset) -> str:
    return f"{file.id}:{file.sha256}:{file.sheet_name or ''}"


def load_frame(file: FileAsset) -> tuple[pd.DataFrame, LoadResult]:
    """带缓存地读取文件（同一文件反复分析不重复解析）。"""
    key = _cache_key(file)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        _, df, meta = _CACHE[key]
        return df, meta

    result = load_dataframe(file.storage_path, sheet_name=file.sheet_name)
    _CACHE[key] = (time.time(), result.df, result)
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return result.df, result


def prime_cache(file: FileAsset, df: pd.DataFrame, meta: LoadResult) -> None:
    """上传时已经解析过一遍，直接放进缓存，分析时不用再读盘。"""
    _CACHE[_cache_key(file)] = (time.time(), df, meta)
    _CACHE.move_to_end(_cache_key(file))
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


def invalidate_cache(file_id: str | None = None) -> None:
    if file_id is None:
        _CACHE.clear()
        return
    for key in [k for k in _CACHE if k.startswith(f"{file_id}:")]:
        _CACHE.pop(key, None)


def run_analysis(
    db: Session,
    file: FileAsset,
    *,
    use_ai: bool = True,
    trigger: str = "manual",
    index_rag: bool = True,
    force: bool = False,
) -> AnalysisRun:
    """跑完整分析流程并保存历史。失败也会落一条 failed 记录，方便前端展示。"""
    if not force:
        existing = (
            db.query(AnalysisRun)
            .filter(AnalysisRun.file_id == file.id, AnalysisRun.status == "succeeded")
            .order_by(AnalysisRun.created_at.desc())
            .first()
        )
        if existing and existing.options.get("use_ai") == use_ai:
            return existing

    run = AnalysisRun(
        file_id=file.id,
        status="running",
        trigger=trigger,
        options={"use_ai": use_ai, "index_rag": index_rag},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    started = time.perf_counter()
    try:
        df, load_meta = load_frame(file)

        profile = profile_dataframe(df, source_name=file.name)
        profile["load"] = {
            "encoding": load_meta.encoding,
            "delimiter": load_meta.delimiter,
            "sheet": load_meta.sheet_name,
            "sheets": load_meta.sheet_names,
            "warnings": load_meta.warnings,
        }

        analysis = analyze_dataframe(df, profile)
        charts = recommend_charts(df, profile, analysis)
        insights = generate_insights(profile, analysis, charts, use_ai=use_ai)

        file.rows = int(df.shape[0])
        file.cols = int(df.shape[1])
        file.sheet_name = load_meta.sheet_name or file.sheet_name
        file.sheet_names = load_meta.sheet_names or file.sheet_names
        file.columns_meta = profile["columns"]
        file.status = "analyzed"
        file.error = None

        run.profile = profile
        run.analysis = analysis
        run.charts = charts
        run.insights = insights
        run.model = insights.get("model", "") if insights.get("engine") == "llm" else ""
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        run.status = "succeeded"
        run.error = None
        db.commit()
        db.refresh(run)

        if index_rag:
            try:
                rag.index_dataset(db, file, df, profile, analysis, charts)
            except Exception:
                # 索引失败不影响分析结果
                db.rollback()

        return run
    except Exception as exc:
        run.status = "failed"
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        raise PipelineError(str(exc)) from exc


def run_payload(run: AnalysisRun, file: FileAsset | None = None) -> dict[str, Any]:
    """把 run 序列化成前端可直接用的结构。"""
    payload: dict[str, Any] = {
        "id": run.id,
        "file_id": run.file_id,
        "file_name": file.name if file else (run.file.name if run.file else ""),
        "status": run.status,
        "trigger": run.trigger,
        "options": run.options,
        "profile": run.profile,
        "analysis": run.analysis,
        "charts": run.charts,
        "insights": run.insights,
        "model": run.model,
        "duration_ms": run.duration_ms,
        "error": run.error,
        "created_at": iso_utc(run.created_at),
    }
    return to_python(payload)
