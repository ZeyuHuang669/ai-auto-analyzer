"""自动数据分析：统计描述、相关性、趋势、分组对比、异常值、关键发现。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.services.loader import infer_types
from app.utils.json import to_python

MAX_CORR_COLS = 8


def _num_cols(df: pd.DataFrame, profile: dict) -> list[str]:
    return [c for c in profile["roles"]["measure"] if c in df.columns]


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(f) >= 1_000_000:
        return f"{f / 1_000_000:.2f}M"
    if abs(f) >= 10_000:
        return f"{f / 1000:.1f}k"
    if f.is_integer():
        return f"{int(f):,}"
    return f"{f:,.{digits}f}"


def _measure_stats(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    out = []
    for col in columns:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
        out.append(
            {
                "column": col,
                "count": int(s.size),
                "mean": float(s.mean()),
                "median": float(s.median()),
                "std": float(s.std()) if s.size > 1 else 0.0,
                "min": float(s.min()),
                "max": float(s.max()),
                "q1": q1,
                "q3": q3,
                "skew": float(s.skew()) if s.size > 2 else 0.0,
                "zero_ratio": float((s == 0).mean()),
            }
        )
    return out


def _correlations(df: pd.DataFrame, columns: list[str]) -> dict:
    cols = [c for c in columns if df[c].nunique(dropna=True) >= 3][:MAX_CORR_COLS]
    if len(cols) < 2:
        return {"pairs": [], "matrix": None}
    corr = df[cols].apply(pd.to_numeric, errors="coerce").corr()

    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            r = corr.loc[a, b]
            if pd.isna(r):
                continue
            strength = (
                "强"
                if abs(r) >= 0.7
                else "中等"
                if abs(r) >= 0.4
                else "弱"
            )
            pairs.append(
                {
                    "a": a,
                    "b": b,
                    "r": round(float(r), 4),
                    "strength": strength,
                    "direction": "正相关" if r > 0 else "负相关",
                }
            )
    pairs.sort(key=lambda p: abs(p["r"]), reverse=True)

    matrix = {
        "labels": cols,
        "z": [[round(float(v), 3) if pd.notna(v) else None for v in row] for row in corr.to_numpy()],
    }
    return {"pairs": pairs[:8], "matrix": matrix}


def _freq_for_span(span_days: int) -> tuple[str, str]:
    if span_days <= 2:
        return "h", "小时"
    if span_days <= 90:
        return "D", "日"
    if span_days <= 1000:
        return "ME", "月"
    return "YE", "年"


def _time_series(df: pd.DataFrame, time_col: str, value_col: str) -> dict:
    tmp = df[[time_col, value_col]].copy()
    tmp[time_col] = pd.to_datetime(tmp[time_col], errors="coerce")
    tmp[value_col] = pd.to_numeric(tmp[value_col], errors="coerce")
    tmp = tmp.dropna()
    if tmp.empty:
        return {}

    span_days = int((tmp[time_col].max() - tmp[time_col].min()).days)
    freq, label = _freq_for_span(span_days)
    grouped = (
        tmp.set_index(time_col)[value_col]
        .resample(freq)
        .sum()
        .dropna()
    )
    if len(grouped) < 2:
        return {}

    values = grouped.to_numpy(dtype=float)
    x = np.arange(len(values))
    slope = float(np.polyfit(x, values, 1)[0]) if len(values) >= 2 else 0.0
    first, last = float(values[0]), float(values[-1])
    pct_change = ((last - first) / abs(first) * 100) if first else None
    ss_res = float(((values - (slope * x + (values.mean() - slope * x.mean()))) ** 2).sum())
    ss_tot = float(((values - values.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0

    return {
        "time_column": time_col,
        "value_column": value_col,
        "freq": freq,
        "freq_label": label,
        "points": [
            {"period": idx.isoformat(), "value": float(val)}
            for idx, val in zip(grouped.index, values)
        ],
        "first": first,
        "last": last,
        "pct_change": round(pct_change, 2) if pct_change is not None else None,
        "slope": slope,
        "r2": round(r2, 3),
        "direction": "上升" if slope > 0 else ("下降" if slope < 0 else "持平"),
    }


def _group_analysis(df: pd.DataFrame, dim: str, measure: str) -> dict:
    tmp = df[[dim, measure]].copy()
    tmp[measure] = pd.to_numeric(tmp[measure], errors="coerce")
    tmp = tmp.dropna()
    if tmp.empty:
        return {}
    agg = (
        tmp.groupby(dim)[measure]
        .agg(count="count", total="sum", mean="mean")
        .sort_values("total", ascending=False)
    )
    top = agg.head(8)
    total_sum = float(agg["total"].sum())
    rows = [
        {
            "group": str(idx),
            "total": float(row["total"]),
            "mean": float(row["mean"]),
            "count": int(row["count"]),
            "share": round(float(row["total"]) / total_sum, 4) if total_sum else 0.0,
        }
        for idx, row in top.iterrows()
    ]
    top_share = rows[0]["share"] if rows else 0.0
    spread = None
    if len(agg) > 1 and float(agg["total"].min()) > 0:
        spread = float(agg["total"].max()) / float(agg["total"].min())
    return {
        "dimension": dim,
        "measure": measure,
        "groups": int(agg.shape[0]),
        "top": rows,
        "best": rows[0]["group"] if rows else None,
        "worst": rows[-1]["group"] if rows else None,
        "top_share": top_share,
        "max_min_ratio": round(spread, 2) if spread else None,
    }


def _findings(df: pd.DataFrame, profile: dict, stats: list[dict], corr: dict,
              trend: dict | None, groups: list[dict]) -> list[dict]:
    findings: list[dict] = []

    def add(kind: str, score: int, title: str, detail: str, columns: list[str],
            metric: Any = None) -> None:
        findings.append(
            {
                "id": f"{kind}-{len(findings)}",
                "kind": kind,
                "score": score,
                "severity": "high" if score >= 70 else "medium" if score >= 45 else "low",
                "title": title,
                "detail": detail,
                "columns": columns,
                "metric": metric,
            }
        )

    # 1. 缺失
    for col in profile["columns"]:
        if col["missing_ratio"] >= 0.2:
            add(
                "missing",
                55 + int(col["missing_ratio"] * 40),
                f"「{col['name']}」缺失较多",
                f"{col['missing']} 行为空（{col['missing_ratio']:.1%}），"
                "做分组统计时该列样本会明显减少。",
                [col["name"]],
                round(col["missing_ratio"], 3),
            )

    # 2. 重复
    if profile["duplicate_ratio"] > 0.01:
        add(
            "duplicate",
            50,
            "存在重复记录",
            f"{profile['duplicate_rows']} 行完全重复（{profile['duplicate_ratio']:.1%}），"
            "求和类指标可能被高估。",
            [],
            profile["duplicate_rows"],
        )

    # 3. 相关性
    for pair in corr.get("pairs", [])[:3]:
        if abs(pair["r"]) >= 0.6:
            add(
                "correlation",
                60 + int(abs(pair["r"]) * 30),
                f"「{pair['a']}」与「{pair['b']}」{pair['direction']}",
                f"相关系数 r = {pair['r']}（{pair['strength']}），"
                + ("两者可能受同一因素驱动，适合放在同一张图里看。"
                   if pair["r"] > 0 else "一个升高时另一个倾向于下降。"),
                [pair["a"], pair["b"]],
                pair["r"],
            )

    # 4. 趋势
    if trend and trend.get("pct_change") is not None:
        pct = trend["pct_change"]
        if abs(pct) >= 15:
            weak_fit = (trend.get("r2") or 0) < 0.15
            detail = (
                f"按{trend['freq_label']}汇总，首尾对比从 {_fmt(trend['first'])} 变为 "
                f"{_fmt(trend['last'])}，变化 {pct:+.1f}%（拟合 R²={trend['r2']}）。"
            )
            if weak_fit:
                detail += "但拟合度较低、期间波动较大，不宜直接当作稳定趋势。"
            add(
                "trend",
                (52 if weak_fit else 58) + min(20, int(abs(pct) / 5)),
                f"「{trend['value_column']}」整体{trend['direction']}",
                detail,
                [trend["time_column"], trend["value_column"]],
                pct,
            )

    # 5. 分组集中度
    for g in groups:
        if g.get("top") and g["top_share"] >= 0.5 and g["groups"] >= 3:
            add(
                "concentration",
                50 + int(g["top_share"] * 30),
                f"「{g['dimension']}」高度集中",
                f"「{g['top'][0]['group']}」占总{g['measure']}的 {g['top_share']:.1%}，"
                f"共 {g['groups']} 个分组。",
                [g["dimension"], g["measure"]],
                g["top_share"],
            )
        if g.get("max_min_ratio") and g["max_min_ratio"] >= 3:
            add(
                "spread",
                52,
                f"「{g['dimension']}」组间差异明显",
                f"最高组是最低组的 {g['max_min_ratio']:.1f} 倍"
                f"（{g['best']} vs {g['worst']}），值得重点看头部。",
                [g["dimension"], g["measure"]],
                g["max_min_ratio"],
            )

    # 6. 偏态与异常值
    for st in stats:
        if abs(st.get("skew") or 0) >= 1.5:
            add(
                "skew",
                46,
                f"「{st['column']}」分布偏斜",
                f"偏度 {st['skew']:.2f}，均值 {_fmt(st['mean'])} 与中位数 "
                f"{_fmt(st['median'])} 差距较大，少数极端值会拉高平均值。",
                [st["column"]],
                st["skew"],
            )
    for col in profile["columns"]:
        st = col.get("stats") or {}
        if st.get("outlier_ratio", 0) >= 0.02:
            add(
                "outlier",
                54,
                f"「{col['name']}」存在异常值",
                f"{st['outliers']} 个点超出 1.5×IQR 范围（{st['outlier_ratio']:.1%}），"
                f"正常区间约 {_fmt(st['q1'])} ~ {_fmt(st['q3'])}。",
                [col["name"]],
                st["outliers"],
            )

    # 7. 常量列
    const = [c["name"] for c in profile["columns"] if c["is_constant"]]
    if const:
        add(
            "constant",
            30,
            "存在常量列",
            f"{'、'.join(const[:5])} 只有一个取值，对分析没有信息量，可以忽略。",
            const[:5],
            len(const),
        )

    # 去重 + 排序：同类发现最多保留 2 条，避免同一维度换个指标就重复刷屏
    seen: set[tuple] = set()
    per_kind: dict[str, int] = {}
    unique: list[dict] = []
    for f in sorted(findings, key=lambda x: x["score"], reverse=True):
        if f["kind"] in ("concentration", "spread"):
            key = (f["kind"], f["columns"][0] if f["columns"] else "")
        elif f["kind"] in ("outlier", "missing", "skew"):
            key = (f["kind"], f["columns"][0] if f["columns"] else "")
        else:
            key = (f["kind"], tuple(f["columns"]))
        if key in seen or per_kind.get(f["kind"], 0) >= 2:
            continue
        seen.add(key)
        per_kind[f["kind"]] = per_kind.get(f["kind"], 0) + 1
        unique.append(f)
    return unique[:12]


def analyze_dataframe(df: pd.DataFrame, profile: dict) -> dict:
    """对数据集做一次完整的自动统计分析与发现提取。"""
    df = infer_types(df)
    measures = _num_cols(df, profile)
    times = [c for c in profile["roles"]["time"] if c in df.columns]
    dims = [c for c in profile["roles"]["dimension"] if c in df.columns]

    stats = _measure_stats(df, measures)
    corr = _correlations(df, measures)

    trend = None
    if times and measures:
        # 多个指标都成立时，选总量最大的那个（业务上更主要），避免小基数指标的巨大百分比抢镜
        candidates: list[dict] = []
        for tcol in times[:2]:
            for mcol in measures[:4]:
                ts = _time_series(df, tcol, mcol)
                if ts:
                    candidates.append(ts)
        if candidates:
            trend = max(
                candidates, key=lambda t: sum(abs(p["value"]) for p in t["points"])
            )

    groups: list[dict] = []
    if dims and measures:
        ranked_dims = sorted(
            dims, key=lambda d: df[d].nunique(dropna=True)
        )[:3]
        for d in ranked_dims:
            for m in measures[:2]:
                g = _group_analysis(df, d, m)
                if g:
                    groups.append(g)

    findings = _findings(df, profile, stats, corr, trend, groups)

    facts = [f["title"] + "：" + f["detail"] for f in findings[:8]]

    return to_python(
        {
            "measures": stats,
            "dimensions": [
                {
                    "column": c["name"],
                    "unique": c["unique"],
                    "top_values": c.get("top_values", []),
                }
                for c in profile["columns"]
                if c["role"] in ("dimension", "flag")
            ][:8],
            "correlations": corr,
            "trend": trend,
            "groups": groups[:4],
            "findings": findings,
            "facts": facts,
        }
    )
