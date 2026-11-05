"""文件存储：保存上传、去重、删除。"""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import UPLOAD_DIR, get_settings
from app.services.loader import SUPPORTED_EXT

settings = get_settings()


class StorageError(RuntimeError):
    pass


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name).strip() or "data.csv"
    return name[:180]


def save_upload(stream: BinaryIO, filename: str) -> tuple[Path, str, int]:
    """把上传流写盘，返回 (路径, sha256, 字节数)。"""
    safe = safe_filename(filename)
    ext = Path(safe).suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise StorageError(
            f"不支持 {ext or '无扩展名'} 格式，支持：{', '.join(sorted(SUPPORTED_EXT))}"
        )

    limit = settings.max_upload_mb * 1024 * 1024
    digest = hashlib.sha256()
    target_dir = UPLOAD_DIR / uuid.uuid4().hex[:12]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe

    size = 0
    with target.open("wb") as fh:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                fh.close()
                shutil.rmtree(target_dir, ignore_errors=True)
                raise StorageError(f"文件超过 {settings.max_upload_mb} MB 限制")
            digest.update(chunk)
            fh.write(chunk)

    if size == 0:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise StorageError("文件是空的")

    return target, digest.hexdigest(), size


def remove_file(path: str | Path) -> None:
    p = Path(path)
    if p.exists():
        p.unlink(missing_ok=True)
    parent = p.parent
    if parent.is_dir() and parent != UPLOAD_DIR and not any(parent.iterdir()):
        parent.rmdir()
