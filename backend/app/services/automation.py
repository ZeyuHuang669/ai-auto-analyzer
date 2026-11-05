"""自动化执行：监视目录，发现新文件自动跑完整分析流水线。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.models import AutomationRule, FileAsset, utcnow
from app.services.loader import SUPPORTED_EXT
from app.services.pipeline import run_analysis

logger = logging.getLogger(__name__)

_IGNORED_PREFIXES = ("~$", ".~", "$")


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def scan_rule(db: Session, rule: AutomationRule, limit: int = 20) -> dict:
    """扫描一条规则，返回本次处理结果。"""
    result = {"rule_id": rule.id, "found": 0, "processed": 0, "skipped": 0, "errors": []}
    watch = Path(rule.watch_dir).expanduser()

    if not watch.exists() or not watch.is_dir():
        rule.last_error = f"监视目录不存在：{watch}"
        rule.last_scanned_at = utcnow()
        db.commit()
        result["errors"].append(rule.last_error)
        return result

    pattern = (rule.pattern or "*").strip() or "*"
    try:
        candidates = sorted(
            (p for p in watch.glob(pattern) if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception as exc:
        rule.last_error = f"遍历目录失败：{exc}"
        db.commit()
        result["errors"].append(rule.last_error)
        return result

    for path in candidates[: limit * 5]:
        if result["processed"] >= limit:
            break
        if path.name.startswith(_IGNORED_PREFIXES):
            continue
        if path.suffix.lower() not in SUPPORTED_EXT:
            continue
        result["found"] += 1

        try:
            sha = file_sha256(path)
        except OSError as exc:
            result["errors"].append(f"{path.name}: {exc}")
            continue

        if db.query(FileAsset).filter(FileAsset.sha256 == sha).first():
            result["skipped"] += 1
            continue

        stat = path.stat()
        asset = FileAsset(
            name=path.name,
            original_name=path.name,
            ext=path.suffix.lower(),
            mime="",
            size_bytes=stat.st_size,
            sha256=sha,
            storage_path=str(path.resolve()),
            status="ready",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        try:
            run_analysis(db, asset, use_ai=rule.use_ai, trigger="automation")
            result["processed"] += 1
            rule.last_run_at = utcnow()
            rule.last_error = None
        except Exception as exc:
            asset.status = "failed"
            asset.error = str(exc)[:1000]
            rule.last_error = f"{path.name}: {exc}"[:1000]
            db.commit()
            result["errors"].append(rule.last_error)

    rule.processed_count = (rule.processed_count or 0) + result["processed"]
    rule.last_scanned_at = utcnow()
    db.commit()
    return result


def scan_all_rules(db: Session) -> list[dict]:
    rules = db.query(AutomationRule).filter(AutomationRule.enabled.is_(True)).all()
    return [scan_rule(db, rule) for rule in rules]


def scan_once() -> list[dict]:
    """同步跑一轮扫描（后台线程 / API 手动触发都用它）。"""
    with session_scope() as db:
        return scan_all_rules(db)


async def automation_loop(interval: int = 60) -> None:
    """常驻协程：每隔 interval 秒扫一轮。"""
    logger.info("自动化扫描已启动，间隔 %s 秒", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            started = time.perf_counter()
            results = await asyncio.to_thread(scan_once)
            processed = sum(r["processed"] for r in results)
            if results:
                logger.info(
                    "自动化扫描完成：%s 条规则，处理 %s 个文件，耗时 %.1fs",
                    len(results), processed, time.perf_counter() - started,
                )
        except asyncio.CancelledError:
            logger.info("自动化扫描已停止")
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception("自动化扫描异常：%s", exc)
            await asyncio.sleep(5)
