"""自动推荐图表 + 自动出图：规则引擎打分，再用 Plotly 直接生成图。

前端拿到的是 figure JSON，直接 st.plotly_chart 渲染，不需要再算一遍数据。
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from app.utils.json import to_python

PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756",
    "#72B7B2", "#EECA3B", "#B279A2", "#9D755D",
]

BASE_LAYOUT = dict(
    template="plotly_white",
    margin=dict(l=48, r=24, t=24, b=48),
    font=dict(family="'Microsoft YaHei', 'PingFang SC', sans-serif", size=13),
    hoverlabel=dict(font_size=12),
    title=dict(x=0.01, xanchor="left", font=dict(size=15)),
)


def _figure(fig: go.Figure, title: str) -> dict:
    """标题由前端卡片承担，避免图内图外重复显示同一句话。"""
    fig.update_layout(**BASE_LAYOUT)
    return json.loads(fig.to_json())


def _fmt(value: float) -> str:
    try:
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if abs(value) >= 10_000:
            return f"{value / 1000:.1f}k"
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _line(df: pd.DataFrame, time_col: str, value_col: str, agg: str = "sum") -> tuple[dict, str]:
    tmp = df[[time_col, value_col]].copy()
    tmp[time_col] = pd.to_datetime(tmp[time_col], errors="coerce")
    tmp[value_col] = pd.to_numeric(tmp[value_col], errors="coerce")
    tmp = tmp.dropna()
    if tmp.empty:
        raise ValueError("无有效时间数据")

    span = int((tmp[time_col].max() - tmp[time_col].min()).days)
    if span <= 1:
        freq, label = "h", "小时"
    elif span <= 90:
        freq, label = "D", "天"
    elif span <= 1000:
        freq, label = "ME", "月"
    else:
        freq, label = "YE", "年"

    series = tmp.set_index(time_col)[value_col].resample(freq).agg(agg).dropna()
    if len(series) < 2:
        raise ValueError("时间点太少，画不了趋势")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[i.isoformat() for i in series.index],
            y=series.to_numpy(dtype=float),
            mode="lines+markers",
            name=agg_label(agg),
            line=dict(width=2.4, color=PALETTE[0]),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(76,120,168,0.12)",
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>",
        )
    )
    fig.update_xaxes(title_text=f"时间（按{label}聚合）", showgrid=False)
    fig.update_yaxes(title_text=f"{value_col}（{agg_label(agg)}）", gridcolor="rgba(0,0,0,0.06)")

    first, last = float(series.iloc[0]), float(series.iloc[-1])
    pct = (last - first) / abs(first) * 100 if first else None
    trend_word = "上升" if last > first else ("下降" if last < first else "持平")
    insight = (
        f"{time_col} 按{label}汇总后，{value_col} 从 {_fmt(first)} 到 {_fmt(last)}，"
        f"整体{trend_word}" + (f"（{pct:+.1f}%）" if pct is not None else "")
    )
    spec = {
        "kind": "line",
        "columns": [time_col, value_col],
        "agg": agg,
        "data": [
            {"period": idx.isoformat(), "value": float(v)}
            for idx, v in zip(series.index, series.to_numpy(dtype=float))
        ],
        "x_label": time_col,
        "y_label": value_col,
        "insight": insight,
    }
    return spec, insight


def agg_label(agg: str) -> str:
    return {"sum": "求和", "mean": "平均", "count": "计数"}.get(agg, agg)


def _bar(df: pd.DataFrame, dim: str, measure: str, agg: str = "sum", top_n: int = 10,
         horizontal: bool = False) -> tuple[dict, str]:
    tmp = df[[dim, measure]].copy()
    tmp[measure] = pd.to_numeric(tmp[measure], errors="coerce")
    tmp = tmp.dropna()
    if tmp.empty:
        raise ValueError("无有效数据")

    grouped = tmp.groupby(dim)[measure].agg(agg).sort_values(ascending=False)
    if grouped.empty:
        raise ValueError("无有效分组")
    shown = grouped.head(top_n)
    labels = [str(i) for i in shown.index]
    values = [float(v) for v in shown.to_numpy()]

    fig = go.Figure(
        go.Bar(
            x=values if horizontal else labels,
            y=labels if horizontal else values,
            orientation="h" if horizontal else "v",
            marker_color=PALETTE[0],
            text=[_fmt(v) for v in values],
            textposition="outside",
            hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>"
            if horizontal
            else "%{x}<br>%{y:,.2f}<extra></extra>",
        )
    )
    axis_title = f"{measure}（{agg_label(agg)}）"
    if horizontal:
        fig.update_xaxes(title_text=axis_title, gridcolor="rgba(0,0,0,0.06)")
        fig.update_yaxes(title_text=dim, autorange="reversed")
    else:
        fig.update_xaxes(title_text=dim, showgrid=False)
        fig.update_yaxes(title_text=axis_title, gridcolor="rgba(0,0,0,0.06)")

    total = float(grouped.sum()) if agg == "sum" else None
    share = (values[0] / total) if total else None
    insight = f"{labels[0]} 的{measure}{agg_label(agg)}最高（{_fmt(values[0])}）"
    if share:
        insight += f"，占全部的 {share:.0%}"
    spec = {
        "kind": "bar",
        "columns": [dim, measure],
        "agg": agg,
        "data": [{"group": l, "value": v} for l, v in zip(labels, values)],
        "x_label": dim,
        "y_label": measure,
        "insight": insight,
    }
    return spec, insight


def _pie(df: pd.DataFrame, dim: str, measure: str) -> tuple[dict, str]:
    tmp = df[[dim, measure]].copy()
    tmp[measure] = pd.to_numeric(tmp[measure], errors="coerce")
    tmp = tmp.dropna()
    grouped = tmp.groupby(dim)[measure].sum().sort_values(ascending=False)
    if grouped.empty or len(grouped) > 8 or float(grouped.sum()) <= 0:
        raise ValueError("不适合饼图")

    top = grouped.head(6)
    rest = float(grouped.iloc[6:].sum())
    labels = [str(i) for i in top.index] + (["其他"] if rest > 0 else [])
    values = [float(v) for v in top.to_numpy()] + ([rest] if rest > 0 else [])

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.45,
            marker=dict(colors=PALETTE),
            textinfo="label+percent",
            hovertemplate="%{label}<br>%{value:,.2f}（%{percent}）<extra></extra>",
        )
    )
    share = values[0] / sum(values)
    insight = f"{labels[0]} 占比最高，约 {share:.0%}，结构上呈头部集中"
    spec = {
        "kind": "pie",
        "columns": [dim, measure],
        "agg": "sum",
        "data": [{"group": l, "value": v} for l, v in zip(labels, values)],
        "x_label": dim,
        "y_label": measure,
        "insight": insight,
    }
    return spec, insight


def _scatter(df: pd.DataFrame, x_col: str, y_col: str, limit: int = 800) -> tuple[dict, str]:
    tmp = df[[x_col, y_col]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(tmp) < 3:
        raise ValueError("有效点太少")
    if len(tmp) > limit:
        tmp = tmp.sample(limit, random_state=42)

    fig = go.Figure(
        go.Scattergl(
            x=tmp[x_col],
            y=tmp[y_col],
            mode="markers",
            marker=dict(size=7, color=PALETTE[2], opacity=0.65,
                        line=dict(width=0.5, color="white")),
            hovertemplate=f"{x_col}: %{{x:,.2f}}<br>{y_col}: %{{y:,.2f}}<extra></extra>",
        )
    )
    # 拟合趋势线
    if len(tmp) >= 5:
        coef = np.polyfit(tmp[x_col].to_numpy(dtype=float), tmp[y_col].to_numpy(dtype=float), 1)
        xs = np.linspace(float(tmp[x_col].min()), float(tmp[x_col].max()), 50)
        fig.add_trace(
            go.Scatter(
                x=xs, y=coef[0] * xs + coef[1], mode="lines",
                line=dict(color=PALETTE[3], width=2, dash="dash"),
                name="趋势线", hoverinfo="skip",
            )
        )
    fig.update_xaxes(title_text=x_col, gridcolor="rgba(0,0,0,0.06)")
    fig.update_yaxes(title_text=y_col, gridcolor="rgba(0,0,0,0.06)")
    r = float(tmp[x_col].corr(tmp[y_col]))
    insight = f"{x_col} 与 {y_col} 的相关系数 r={r:.2f}，呈{'正' if r > 0 else '负'}相关"
    spec = {
        "kind": "scatter",
        "columns": [x_col, y_col],
        "data": [{"x": float(a), "y": float(b)} for a, b in zip(tmp[x_col], tmp[y_col])],
        "x_label": x_col,
        "y_label": y_col,
        "insight": insight,
    }
    return spec, insight


def _histogram(df: pd.DataFrame, col: str, bins: int = 24) -> tuple[dict, str]:
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        raise ValueError("无有效数值")
    counts, edges = np.histogram(s.to_numpy(dtype=float), bins=min(bins, max(5, s.nunique())))
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
    fig = go.Figure(
        go.Bar(
            x=centers,
            y=counts,
            width=[(edges[i + 1] - edges[i]) * 0.92 for i in range(len(counts))],
            marker_color=PALETTE[4],
            hovertemplate="区间 %{x:,.2f}<br>数量 %{y}<extra></extra>",
        )
    )
    fig.update_xaxes(title_text=col, gridcolor="rgba(0,0,0,0.06)")
    fig.update_yaxes(title_text="记录数", gridcolor="rgba(0,0,0,0.06)")
    mode_bin = centers[int(np.argmax(counts))]
    insight = f"{col} 的分布集中在 {_fmt(mode_bin)} 附近，中位数 {_fmt(float(s.median()))}"
    spec = {
        "kind": "histogram",
        "columns": [col],
        "data": [
            {"bin_center": float(c), "bin_start": float(edges[i]), "count": int(counts[i])}
            for i, c in enumerate(centers)
        ],
        "x_label": col,
        "y_label": "记录数",
        "insight": insight,
    }
    return spec, insight


def _box(df: pd.DataFrame, dim: str, measure: str, max_groups: int = 6) -> tuple[dict, str]:
    tmp = df[[dim, measure]].copy()
    tmp[measure] = pd.to_numeric(tmp[measure], errors="coerce")
    tmp = tmp.dropna()
    if tmp.empty:
        raise ValueError("无有效数据")
    order = tmp.groupby(dim)[measure].median().sort_values(ascending=False).head(max_groups).index
    fig = go.Figure()
    for i, group in enumerate(order):
        vals = tmp.loc[tmp[dim] == group, measure]
        fig.add_trace(
            go.Box(
                y=vals.to_numpy(dtype=float),
                name=str(group),
                marker_color=PALETTE[i % len(PALETTE)],
                boxpoints="outliers",
            )
        )
    fig.update_xaxes(title_text=dim, showgrid=False)
    fig.update_yaxes(title_text=measure, gridcolor="rgba(0,0,0,0.06)")
    insight = f"按 {dim} 分组看 {measure} 的分布，比较各组的中位数与离散程度"
    spec = {
        "kind": "box",
        "columns": [dim, measure],
        "data": [
            {
                "group": str(g),
                "values": tmp.loc[tmp[dim] == g, measure].head(200).tolist(),
            }
            for g in order
        ],
        "x_label": dim,
        "y_label": measure,
        "insight": insight,
    }
    return spec, insight


def _heatmap(matrix: dict) -> tuple[dict, str]:
    labels = matrix["labels"]
    z = matrix["z"]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=labels,
            y=labels,
            colorscale="RdBu",
            zmid=0,
            zmin=-1,
            zmax=1,
            text=[[f"{v:.2f}" if v is not None else "" for v in row] for row in z],
            texttemplate="%{text}",
            hovertemplate="%{x} × %{y}<br>r = %{z:.2f}<extra></extra>",
        )
    )
    fig.update_xaxes(tickangle=-35, showgrid=False)
    fig.update_yaxes(showgrid=False)
    insight = "颜色越深相关性越强，红色为正相关、蓝色为负相关"
    spec = {
        "kind": "heatmap",
        "columns": labels,
        "data": {"labels": labels, "z": z},
        "x_label": "字段",
        "y_label": "字段",
        "insight": insight,
    }
    return spec, insight


def _missing_chart(profile: dict) -> tuple[dict, str] | None:
    cols = [c for c in profile["columns"] if c["missing_ratio"] > 0]
    if not cols:
        return None
    cols = sorted(cols, key=lambda c: c["missing_ratio"], reverse=True)[:12]
    names = [c["name"] for c in cols]
    ratios = [c["missing_ratio"] * 100 for c in cols]
    fig = go.Figure(
        go.Bar(
            x=ratios,
            y=names,
            orientation="h",
            marker_color=PALETTE[3],
            text=[f"{r:.1f}%" for r in ratios],
            textposition="outside",
            hovertemplate="%{y}<br>缺失 %{x:.1f}%<extra></extra>",
        )
    )
    fig.update_xaxes(title_text="缺失率（%）", gridcolor="rgba(0,0,0,0.06)")
    fig.update_yaxes(title_text="", autorange="reversed")
    insight = f"缺失最严重的是 {names[0]}（{ratios[0]:.1f}%）"
    return {
        "kind": "missing",
        "columns": names,
        "data": [{"column": n, "missing_ratio": r} for n, r in zip(names, ratios)],
        "x_label": "缺失率（%）",
        "y_label": "",
        "insight": insight,
    }, insight


def recommend_charts(
    df: pd.DataFrame,
    profile: dict,
    analysis: dict,
    limit: int = 6,
) -> list[dict]:
    """根据字段角色与统计结果，自动挑图、自动画图、给出一句话解读。"""
    measures = [c for c in profile["roles"]["measure"] if c in df.columns]
    times = [c for c in profile["roles"]["time"] if c in df.columns]
    dims = [
        c
        for c in profile["roles"]["dimension"]
        if c in df.columns and 2 <= df[c].nunique(dropna=True) <= 50
    ]
    dims = sorted(dims, key=lambda d: df[d].nunique(dropna=True))

    candidates: list[tuple[float, dict]] = []

    def try_add(score: float, title: str, reason: str, builder, *args, **kwargs) -> None:
        try:
            spec, insight = builder(*args, **kwargs)
        except Exception:
            return
        spec.update(
            {
                "id": f"{spec['kind']}-{len(candidates)}",
                "title": title,
                "reason": reason,
                "priority": round(score, 1),
                "insight": insight,
            }
        )
        candidates.append((score, spec))

    # 1) 时间趋势
    for i, tcol in enumerate(times[:2]):
        for j, mcol in enumerate(measures[:2]):
            try_add(
                95 - i * 8 - j * 4,
                f"{mcol} 随时间变化",
                f"检测到时间字段「{tcol}」与数值指标「{mcol}」，趋势图最能体现变化",
                _line, df, tcol, mcol, "sum",
            )

    # 2) 分类对比
    for i, d in enumerate(dims[:3]):
        for j, m in enumerate(measures[:2]):
            horizontal = df[d].nunique(dropna=True) > 6
            try_add(
                86 - i * 6 - j * 4,
                f"各{d}的{m}对比",
                f"「{d}」有 {df[d].nunique(dropna=True)} 个分类，适合用柱状图横向比较",
                _bar, df, d, m, "sum", 10, horizontal,
            )
            if df[d].nunique(dropna=True) <= 6 and m == measures[0]:
                try_add(
                    62 - i * 4,
                    f"{m}在{d}上的结构占比",
                    "分类数较少且数值非负，饼图适合展示占比结构",
                    _pie, df, d, m,
                )

    # 3) 相关性散点
    for pair in analysis.get("correlations", {}).get("pairs", [])[:2]:
        if abs(pair["r"]) >= 0.5:
            try_add(
                80 + abs(pair["r"]) * 10,
                f"{pair['a']} 与 {pair['b']} 的关系",
                f"两者相关系数 {pair['r']}，散点图可以看出线性关系与离群点",
                _scatter, df, pair["a"], pair["b"],
            )

    # 4) 相关性热力图
    matrix = analysis.get("correlations", {}).get("matrix")
    if matrix and len(matrix["labels"]) >= 3:
        try_add(
            72,
            "数值字段相关性热力图",
            "字段数 ≥ 3，热力图能一屏看清所有两两相关",
            _heatmap, matrix,
        )

    # 5) 单指标分布
    for i, m in enumerate(measures[:2]):
        try_add(
            66 - i * 5,
            f"{m} 的分布",
            "单个数值指标适合用直方图看分布形态与集中区间",
            _histogram, df, m,
        )

    # 6) 分组分布（箱线图）
    if dims and measures and df[dims[0]].nunique(dropna=True) <= 8:
        try_add(
            58,
            f"不同{dims[0]}的{measures[0]}分布",
            "箱线图能对比各组中位数、四分位与离群值",
            _box, df, dims[0], measures[0],
        )

    # 7) 缺失情况
    missing = _missing_chart(profile)
    if missing and profile["missing_ratio"] > 0.01:
        spec, insight = missing
        spec.update(
            {
                "id": f"missing-{len(candidates)}",
                "title": "字段缺失率",
                "reason": "存在缺失值，先看清哪些字段受影响最大",
                "priority": 50,
                "insight": insight,
            }
        )
        candidates.append((50, spec))

    # 去重（同 kind + 同字段组合）+ 控制类型多样性：同类图最多 2 张
    seen: set[tuple] = set()
    per_kind: dict[str, int] = {}
    chosen: list[dict] = []
    for _, spec in sorted(candidates, key=lambda x: x[0], reverse=True):
        key = (spec["kind"], tuple(spec["columns"]))
        if key in seen:
            continue
        if per_kind.get(spec["kind"], 0) >= 2:
            continue
        seen.add(key)
        per_kind[spec["kind"]] = per_kind.get(spec["kind"], 0) + 1
        spec["figure"] = _figure_from_spec(spec)
        chosen.append(spec)
        if len(chosen) >= limit:
            break

    return to_python(chosen)


def build_chart(kind: str, df: pd.DataFrame, title: str, reason: str, **kwargs) -> dict | None:
    """按指定类型直接画一张图（供 Planner 使用）。"""
    builders = {
        "line": (_line, ("time_col", "value_col")),
        "bar": (_bar, ("dim", "measure")),
        "pie": (_pie, ("dim", "measure")),
        "scatter": (_scatter, ("x_col", "y_col")),
        "histogram": (_histogram, ("col",)),
        "box": (_box, ("dim", "measure")),
    }
    if kind not in builders:
        return None
    builder, required = builders[kind]
    args = [df] + [kwargs[key] for key in required]
    try:
        spec, insight = builder(*args)
    except Exception:
        return None
    spec.update(
        {
            "id": f"{kind}-adhoc",
            "title": title,
            "reason": reason,
            "priority": 100,
            "insight": insight,
        }
    )
    spec["figure"] = _figure_from_spec(spec)
    return to_python(spec)


def _figure_from_spec(spec: dict) -> dict:
    """按 spec 重新画一次图（数据已算好，这里只负责视觉）。"""
    kind = spec["kind"]
    title = spec["title"]
    fig = go.Figure()

    if kind == "line":
        data = spec["data"]
        fig.add_trace(
            go.Scatter(
                x=[d["period"] for d in data],
                y=[d["value"] for d in data],
                mode="lines+markers",
                line=dict(width=2.4, color=PALETTE[0]),
                marker=dict(size=6),
                fill="tozeroy",
                fillcolor="rgba(76,120,168,0.12)",
                hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>",
            )
        )
        fig.update_xaxes(title_text=spec["x_label"], showgrid=False)
        fig.update_yaxes(title_text=spec["y_label"], gridcolor="rgba(0,0,0,0.06)")

    elif kind == "bar":
        horizontal = spec.get("x_label") and spec.get("y_label") and len(spec["data"]) > 6
        labels = [d["group"] for d in spec["data"]]
        values = [d["value"] for d in spec["data"]]
        fig.add_trace(
            go.Bar(
                x=values if horizontal else labels,
                y=labels if horizontal else values,
                orientation="h" if horizontal else "v",
                marker_color=PALETTE[0],
                text=[_fmt(v) for v in values],
                textposition="outside",
            )
        )
        if horizontal:
            fig.update_xaxes(title_text=spec["y_label"], gridcolor="rgba(0,0,0,0.06)")
            fig.update_yaxes(title_text=spec["x_label"], autorange="reversed")
        else:
            fig.update_xaxes(title_text=spec["x_label"], showgrid=False)
            fig.update_yaxes(title_text=spec["y_label"], gridcolor="rgba(0,0,0,0.06)")

    elif kind == "pie":
        fig.add_trace(
            go.Pie(
                labels=[d["group"] for d in spec["data"]],
                values=[d["value"] for d in spec["data"]],
                hole=0.45,
                marker=dict(colors=PALETTE),
                textinfo="label+percent",
            )
        )

    elif kind == "scatter":
        fig.add_trace(
            go.Scattergl(
                x=[d["x"] for d in spec["data"]],
                y=[d["y"] for d in spec["data"]],
                mode="markers",
                marker=dict(size=7, color=PALETTE[2], opacity=0.65,
                            line=dict(width=0.5, color="white")),
            )
        )
        fig.update_xaxes(title_text=spec["x_label"], gridcolor="rgba(0,0,0,0.06)")
        fig.update_yaxes(title_text=spec["y_label"], gridcolor="rgba(0,0,0,0.06)")

    elif kind == "histogram":
        fig.add_trace(
            go.Bar(
                x=[d["bin_center"] for d in spec["data"]],
                y=[d["count"] for d in spec["data"]],
                marker_color=PALETTE[4],
            )
        )
        fig.update_xaxes(title_text=spec["x_label"], gridcolor="rgba(0,0,0,0.06)")
        fig.update_yaxes(title_text=spec["y_label"], gridcolor="rgba(0,0,0,0.06)")

    elif kind == "box":
        for i, group in enumerate(spec["data"]):
            fig.add_trace(
                go.Box(
                    y=group["values"],
                    name=group["group"],
                    marker_color=PALETTE[i % len(PALETTE)],
                    boxpoints="outliers",
                )
            )
        fig.update_xaxes(title_text=spec["x_label"], showgrid=False)
        fig.update_yaxes(title_text=spec["y_label"], gridcolor="rgba(0,0,0,0.06)")

    elif kind == "heatmap":
        fig.add_trace(
            go.Heatmap(
                z=spec["data"]["z"],
                x=spec["data"]["labels"],
                y=spec["data"]["labels"],
                colorscale="RdBu",
                zmid=0,
                zmin=-1,
                zmax=1,
            )
        )
        fig.update_xaxes(tickangle=-35, showgrid=False)
        fig.update_yaxes(showgrid=False)

    elif kind == "missing":
        fig.add_trace(
            go.Bar(
                x=[d["missing_ratio"] for d in spec["data"]],
                y=[d["column"] for d in spec["data"]],
                orientation="h",
                marker_color=PALETTE[3],
            )
        )
        fig.update_xaxes(title_text="缺失率（%）", gridcolor="rgba(0,0,0,0.06)")
        fig.update_yaxes(autorange="reversed")

    return _figure(fig, title)
