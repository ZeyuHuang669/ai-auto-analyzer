"""自动识别数据：结构、字段角色、质量评分。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.services.loader import infer_types
from app.utils.json import to_python

ROLE_LABEL = {
    "time": "时间",
    "measure": "数值指标",
    "dimension": "分类维度",
    "flag": "布尔标记",
    "text": "文本",
    "id": "标识",
}

_ID_HINTS = ("id", "编号", "序号", "代码", "code", "key", "uuid", "订单号", "单号")
_TIME_HINTS = ("date", "time", "日期", "时间", "年月", "月份", "timestamp")


def _is_numeric(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)


def _is_datetime(s: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(s)


def _is_bool(s: pd.Series) -> bool:
    return pd.api.types.is_bool_dtype(s)


def _is_text(s: pd.Series) -> bool:
    return pd.api.types.is_string_dtype(s) or s.dtype == object


def _name_hits(name: str, hints: tuple[str, ...]) -> bool:
    low = name.lower()
    return any(h in low for h in hints)


def infer_role(series: pd.Series, name: str, n_rows: int) -> str:
    s = series
    if _is_datetime(s):
        return "time"
    if _is_bool(s):
        return "flag"

    non_null = int(s.notna().sum())
    unique = int(s.nunique(dropna=True))
    unique_ratio = unique / non_null if non_null else 0.0

    if _is_numeric(s):
        if _name_hits(name, _ID_HINTS):
            return "id"
        if pd.api.types.is_integer_dtype(s) and unique_ratio > 0.98:
            # 唯一、连续、且从 0/1 开始的整数列，基本就是行号/主键；
            # 从其它值开始（如销量 10,11,12…）仍按指标处理
            if unique == n_rows and n_rows > 3:
                values = np.sort(s.dropna().to_numpy())
                diffs = np.diff(values)
                if len(diffs) and np.all(diffs == 1) and values[0] in (0, 1):
                    return "id"
        return "measure"

    if _is_text(s):
        if unique_ratio > 0.98 and n_rows > 10:
            return "id"
        if unique <= min(50, max(2, int(n_rows * 0.5))):
            return "dimension"
        return "text"
    return "text"


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _numeric_stats(s: pd.Series) -> dict:
    values = pd.to_numeric(s, errors="coerce").dropna()
    if values.empty:
        return {}
    q1, q3 = float(values.quantile(0.25)), float(values.quantile(0.75))
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = int(((values < lower) | (values > upper)).sum())
    return {
        "count": int(values.size),
        "mean": _safe_float(values.mean()),
        "median": _safe_float(values.median()),
        "std": _safe_float(values.std()),
        "min": _safe_float(values.min()),
        "max": _safe_float(values.max()),
        "q1": _safe_float(q1),
        "q3": _safe_float(q3),
        "sum": _safe_float(values.sum()),
        "skew": _safe_float(values.skew()),
        "outliers": outliers,
        "outlier_ratio": round(outliers / values.size, 4) if values.size else 0.0,
    }


def _top_values(s: pd.Series, limit: int = 8) -> list[dict]:
    counts = s.dropna().value_counts().head(limit)
    total = int(s.notna().sum())
    out = []
    for key, cnt in counts.items():
        out.append(
            {
                "value": str(key) if not isinstance(key, (int, float)) else key,
                "count": int(cnt),
                "share": round(cnt / total, 4) if total else 0.0,
            }
        )
    return out


def _time_stats(s: pd.Series) -> dict:
    dates = pd.to_datetime(s, errors="coerce").dropna()
    if dates.empty:
        return {}
    span_days = (dates.max() - dates.min()).days
    granularity = "日"
    if span_days > 365 * 3:
        granularity = "年"
    elif span_days > 120:
        granularity = "月"
    elif span_days <= 3:
        granularity = "小时/更细"
    return {
        "min": dates.min().isoformat(),
        "max": dates.max().isoformat(),
        "span_days": int(span_days),
        "granularity": granularity,
    }


def _column_profile(series: pd.Series, name: str, n_rows: int) -> dict:
    role = infer_role(series, name, n_rows)
    non_null = int(series.notna().sum())
    unique = int(series.nunique(dropna=True))
    missing = n_rows - non_null
    item: dict[str, Any] = {
        "name": name,
        "dtype": str(series.dtype),
        "role": role,
        "role_label": ROLE_LABEL.get(role, role),
        "missing": missing,
        "missing_ratio": round(missing / n_rows, 4) if n_rows else 0.0,
        "unique": unique,
        "unique_ratio": round(unique / non_null, 4) if non_null else 0.0,
        "is_constant": unique <= 1,
        "sample": [to_python(v) for v in series.dropna().head(5).tolist()],
    }
    if role == "measure":
        item["stats"] = _numeric_stats(series)
    elif role == "time":
        item["time"] = _time_stats(series)
    elif role in ("dimension", "flag"):
        item["top_values"] = _top_values(series)
    elif role == "text":
        lengths = series.dropna().astype(str).str.len()
        item["text_stats"] = {
            "avg_len": _safe_float(lengths.mean()),
            "max_len": int(lengths.max()) if not lengths.empty else 0,
        }
        item["top_values"] = _top_values(series, 5)
    return item


def _quality(profile: dict) -> dict:
    rows = profile["rows"] or 1
    cols = profile["cols"] or 1
    missing_ratio = profile["missing_ratio"]
    dup_ratio = profile["duplicate_ratio"]
    constant_cols = sum(1 for c in profile["columns"] if c["is_constant"])

    issues: list[dict] = []
    score = 100.0
    score -= missing_ratio * 55
    score -= dup_ratio * 25
    score -= (constant_cols / cols) * 20

    if missing_ratio > 0.15:
        issues.append(
            {
                "kind": "missing",
                "severity": "high" if missing_ratio > 0.3 else "medium",
                "title": "缺失值偏多",
                "detail": f"整体缺失率 {missing_ratio:.1%}，共 {profile['missing_cells']} 个空单元格",
            }
        )
    if dup_ratio > 0.01:
        issues.append(
            {
                "kind": "duplicate",
                "severity": "medium",
                "title": "存在重复行",
                "detail": f"重复行 {profile['duplicate_rows']} 条（{dup_ratio:.1%}）",
            }
        )
    if constant_cols:
        names = [c["name"] for c in profile["columns"] if c["is_constant"]][:5]
        issues.append(
            {
                "kind": "constant",
                "severity": "low",
                "title": "存在常量列",
                "detail": f"{constant_cols} 个列只有单一取值：{('、'.join(names))}",
            }
        )
    if rows < 30:
        issues.append(
            {
                "kind": "small",
                "severity": "low",
                "title": "样本量偏小",
                "detail": f"仅 {rows} 行，统计结论的稳定性有限",
            }
        )

    score = max(0.0, min(100.0, score))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"
    return {"score": round(score, 1), "grade": grade, "issues": issues}


def _dataset_kind(roles: dict[str, list[str]]) -> str:
    if roles["time"] and roles["measure"]:
        return "时间序列"
    if roles["dimension"] and roles["measure"]:
        return "分类汇总表"
    if len(roles["measure"]) >= 2:
        return "数值明细表"
    if roles["text"]:
        return "文本明细表"
    return "通用表格"


def profile_dataframe(df: pd.DataFrame, source_name: str = "") -> dict:
    """识别数据集结构、字段语义与质量。"""
    # 允许直接传原始 DataFrame：这里再做一次类型推断，保证日期/数值能被识别
    df = infer_types(df)
    n_rows, n_cols = df.shape
    duplicate_rows = int(df.duplicated().sum()) if n_rows else 0
    missing_cells = int(df.isna().sum().sum())
    total_cells = max(1, n_rows * n_cols)

    columns = [_column_profile(df[col], str(col), n_rows) for col in df.columns]
    roles: dict[str, list[str]] = {
        "time": [],
        "measure": [],
        "dimension": [],
        "flag": [],
        "text": [],
        "id": [],
    }
    for col in columns:
        roles[col["role"]].append(col["name"])

    profile: dict[str, Any] = {
        "source": source_name,
        "rows": int(n_rows),
        "cols": int(n_cols),
        "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1024 / 1024, 3),
        "duplicate_rows": duplicate_rows,
        "duplicate_ratio": round(duplicate_rows / n_rows, 4) if n_rows else 0.0,
        "missing_cells": missing_cells,
        "missing_ratio": round(missing_cells / total_cells, 4),
        "columns": columns,
        "roles": roles,
        "kind": _dataset_kind(roles),
        "measured_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    profile["quality"] = _quality(profile)

    summary = [
        f"共 {n_rows:,} 行 × {n_cols} 列（{profile['memory_mb']} MB），识别为「{profile['kind']}」",
        f"时间字段 {len(roles['time'])} 个｜数值指标 {len(roles['measure'])} 个｜"
        f"分类维度 {len(roles['dimension'])} 个｜文本字段 {len(roles['text'])} 个",
        f"缺失率 {profile['missing_ratio']:.2%}，重复行 {duplicate_rows} 条，"
        f"质量评分 {profile['quality']['score']}（{profile['quality']['grade']}）",
    ]
    if roles["time"]:
        summary.append(f"时间列：{'、'.join(roles['time'][:3])}")
    if roles["measure"]:
        summary.append(f"主要指标：{'、'.join(roles['measure'][:5])}")
    profile["summary"] = summary
    return to_python(profile)


def columns_frame(profile: dict) -> pd.DataFrame:
    """把字段画像转成前端表格。"""
    rows = []
    for col in profile.get("columns", []):
        stats = col.get("stats") or {}
        rows.append(
            {
                "字段": col["name"],
                "类型": col["role_label"],
                "缺失率": f"{col['missing_ratio']:.1%}",
                "唯一值": col["unique"],
                "均值": stats.get("mean"),
                "中位数": stats.get("median"),
                "最大": stats.get("max"),
                "最小值": stats.get("min"),
                "样例": "、".join(str(v) for v in col.get("sample", [])[:3]),
            }
        )
    return pd.DataFrame(rows)
