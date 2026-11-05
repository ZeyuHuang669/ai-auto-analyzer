"""序列化辅助：把 ORM 对象转成前端友好的 dict。"""

from __future__ import annotations

from app.models import AnalysisRun, AutomationRule, FileAsset, RagChunk
from app.utils.json import iso_utc, to_python


def file_dict(f: FileAsset, *, detail: bool = False) -> dict:
    data = {
        "id": f.id,
        "name": f.name,
        "original_name": f.original_name,
        "ext": f.ext,
        "size_bytes": f.size_bytes,
        "sha256": f.sha256,
        "rows": f.rows,
        "cols": f.cols,
        "sheet_name": f.sheet_name,
        "sheet_names": f.sheet_names,
        "status": f.status,
        "error": f.error,
        "created_at": iso_utc(f.created_at),
    }
    if detail:
        data["columns"] = f.columns_meta
        data["storage_path"] = f.storage_path
    return to_python(data)


def run_dict(run: AnalysisRun, file_name: str = "", *, with_content: bool = True) -> dict:
    data = {
        "id": run.id,
        "file_id": run.file_id,
        "file_name": file_name or (run.file.name if run.file else ""),
        "status": run.status,
        "trigger": run.trigger,
        "model": run.model,
        "duration_ms": run.duration_ms,
        "error": run.error,
        "created_at": iso_utc(run.created_at),
    }
    if with_content:
        data.update(
            {
                "options": run.options,
                "profile": run.profile,
                "analysis": run.analysis,
                "charts": run.charts,
                "insights": run.insights,
            }
        )
    return to_python(data)


def rule_dict(rule: AutomationRule) -> dict:
    return to_python(
        {
            "id": rule.id,
            "name": rule.name,
            "watch_dir": rule.watch_dir,
            "pattern": rule.pattern,
            "enabled": rule.enabled,
            "use_ai": rule.use_ai,
            "interval_seconds": rule.interval_seconds,
            "last_run_at": iso_utc(rule.last_run_at),
            "last_scanned_at": iso_utc(rule.last_scanned_at),
            "last_error": rule.last_error,
            "processed_count": rule.processed_count,
            "created_at": iso_utc(rule.created_at),
        }
    )


def chunk_dict(chunk: RagChunk) -> dict:
    return to_python(
        {
            "id": chunk.id,
            "file_id": chunk.file_id,
            "kind": chunk.kind,
            "title": chunk.title,
            "content": chunk.content,
            "meta": chunk.meta,
        }
    )
