"""JSON 清洗工具：把 numpy / pandas / datetime 转成可安全序列化的 Python 原生类型。

FastAPI 的 JSONResponse 使用 allow_nan=False，任何 NaN/Inf 都会导致 500，
所以所有要入库或返回的 dict 都必须先过一遍 to_python()。
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


def _clean_scalar(value: Any) -> Any:
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float, Decimal)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(value, (np.datetime64, pd.Timestamp, datetime)):
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            return None
        return ts.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def to_python(obj: Any, _depth: int = 0) -> Any:
    """递归地把对象转成 JSON 安全的纯 Python 结构。"""
    if _depth > 30:
        return str(obj)
    if obj is None:
        return None
    if isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, (float, np.floating, Decimal, np.integer, np.bool_)):
        return _clean_scalar(obj)
    if isinstance(obj, dict):
        return {str(k): to_python(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_python(v, _depth + 1) for v in obj]
    if isinstance(obj, (pd.Series, pd.Index, np.ndarray)):
        return [to_python(v, _depth + 1) for v in obj.tolist()]
    if isinstance(obj, pd.DataFrame):
        return to_python(obj.to_dict(orient="records"), _depth + 1)
    cleaned = _clean_scalar(obj)
    if cleaned is not obj:
        return cleaned
    return str(obj)


def json_safe(obj: Any) -> Any:
    """带 NaN 兜底的序列化前处理。"""
    return to_python(obj)


def iso_utc(dt: datetime | None) -> str | None:
    """统一输出带时区的 ISO 时间。

    SQLite 会丢掉 tzinfo，这里把裸 datetime 当作 UTC 处理，
    前端再按本地时区展示，避免出现"时间差 8 小时"。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()
