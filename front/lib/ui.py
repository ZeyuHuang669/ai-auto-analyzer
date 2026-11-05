"""Streamlit 渲染组件：把后端返回的分析结果画成页面。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd
import plotly.io as pio
import streamlit as st

from lib import api


def fmt_time(value: str | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """后端给的是 UTC ISO 时间，这里转成本地时区展示。"""
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)[:19].replace("T", " ")
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime(fmt)

STATUS_TEXT = {
    "ready": "已就绪",
    "parsed": "已解析",
    "uploaded": "已上传",
    "parsing": "解析中",
    "analyzed": "已分析",
    "failed": "失败",
    "succeeded": "已完成",
    "running": "分析中",
    "pending": "排队中",
}

SEVERITY = {"high": "🔴", "medium": "🟠", "low": "🔵"}

TRIGGER_TEXT = {"manual": "手动", "automation": "自动", "api": "接口", "index": "建索引"}


def chip(label: str, color: str = "#4C78A8") -> str:
    return (
        f"<span style='background:{color}1a;color:{color};border:1px solid {color}55;"
        f"border-radius:999px;padding:1px 10px;font-size:0.8rem;margin-right:6px;"
        f"white-space:nowrap'>{label}</span>"
    )


def fmt_bytes(size: int | float | None) -> str:
    size = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def plotly(fig_json: dict, height: int = 380, key: str | None = None) -> None:
    fig = pio.from_json(json.dumps(fig_json, ensure_ascii=False))
    fig.update_layout(height=height)
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except TypeError:  # 兼容旧版 Streamlit
        st.plotly_chart(fig, use_container_width=True, key=key)


def table(df: pd.DataFrame, key: str | None = None) -> None:
    try:
        st.dataframe(df, width="stretch", hide_index=True, key=key)
    except TypeError:  # 兼容旧版 Streamlit
        st.dataframe(df, use_container_width=True, hide_index=True, key=key)


def profile_frame(profile: dict) -> pd.DataFrame:
    rows = []
    for col in profile.get("columns", []):
        stats = col.get("stats") or {}
        rows.append(
            {
                "字段": col["name"],
                "识别类型": col["role_label"],
                "缺失率": f"{col['missing_ratio']:.1%}" if col["missing_ratio"] else "—",
                "唯一值": col["unique"],
                "均值": _round(stats.get("mean")),
                "中位数": _round(stats.get("median")),
                "最小": _round(stats.get("min")),
                "最大": _round(stats.get("max")),
                "样例": "、".join(str(v) for v in col.get("sample", [])[:3]),
            }
        )
    return pd.DataFrame(rows)


def _round(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def summary_frame(runs: list[dict]) -> pd.DataFrame:
    rows = []
    for r in runs:
        rows.append(
            {
                "时间": fmt_time(r.get("created_at")),
                "文件": r.get("file_name") or "",
                "状态": STATUS_TEXT.get(r.get("status", ""), r.get("status", "")),
                "方式": TRIGGER_TEXT.get(r.get("trigger", ""), r.get("trigger", "")),
                "图表": r.get("charts_count", 0),
                "耗时(ms)": r.get("duration_ms", 0),
            }
        )
    return pd.DataFrame(rows)


def empty_state(title: str, text: str, page: str | None = None, label: str = "去上传") -> None:
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.write(text)
        if page:
            st.page_link(page, label=label)


# --------------------------------------------------------------------------- #
# 分析结果
# --------------------------------------------------------------------------- #
def render_run(run: dict, key_prefix: str = "run") -> None:
    profile = run.get("profile") or {}
    analysis = run.get("analysis") or {}
    charts = run.get("charts") or []
    insights = run.get("insights") or {}

    status = run.get("status", "")
    st.markdown(
        chip(STATUS_TEXT.get(status, status), "#54A24B" if status == "succeeded" else "#E45756")
        + chip(TRIGGER_TEXT.get(run.get("trigger", ""), run.get("trigger", "")), "#888")
        + chip(fmt_time(run.get("created_at"), "%Y-%m-%d %H:%M"), "#888")
        + chip(
            "模型生成" if insights.get("engine") == "llm" else "规则兜底",
            "#4C78A8" if insights.get("engine") == "llm" else "#999",
        ),
        unsafe_allow_html=True,
    )

    if status == "failed":
        st.error(f"分析失败：{run.get('error')}")
        return

    quality = profile.get("quality", {})
    cols = st.columns(5)
    cols[0].metric("数据行数", f"{profile.get('rows', 0):,}")
    cols[1].metric("字段数", profile.get("cols", 0))
    cols[2].metric("缺失率", f"{profile.get('missing_ratio', 0):.1%}")
    cols[3].metric(f"质量评分（{quality.get('grade', '—')} 级）", quality.get("score", 0))
    cols[4].metric("图表 / 发现", f"{len(charts)} / {len(analysis.get('findings', []))}")

    tabs = st.tabs(["📊 智能图表", "🔍 关键发现", "🧬 数据识别", "🤖 AI 结论", "👀 数据预览"])

    with tabs[0]:
        render_charts(charts, key_prefix=key_prefix)

    with tabs[1]:
        render_findings(analysis.get("findings", []))

    with tabs[2]:
        render_profile(profile)

    with tabs[3]:
        render_insights(insights)

    with tabs[4]:
        render_preview(run.get("file_id", ""), key_prefix)


def render_charts(charts: list[dict], key_prefix: str = "c", preview: int = 3) -> None:
    if not charts:
        st.info("这份数据没有匹配到合适的图表（可能字段太少）。")
        return

    for i, chart in enumerate(charts[:preview]):
        with st.container(border=True):
            st.markdown(f"**{chart['title']}**")
            st.caption(f"为什么选它：{chart['reason']}")
            plotly(chart["figure"], key=f"{key_prefix}-chart-{i}")
            st.caption(f"💡 {chart['insight']}")

    rest = charts[preview:]
    if rest:
        with st.expander(f"更多图表（{len(rest)} 张）", expanded=False):
            for j, chart in enumerate(rest, start=preview):
                st.markdown(f"**{chart['title']}**")
                st.caption(f"为什么选它：{chart['reason']}")
                plotly(chart["figure"], height=340, key=f"{key_prefix}-chart-{j}")
                st.caption(f"💡 {chart['insight']}")


def render_findings(findings: list[dict]) -> None:
    if not findings:
        st.info("没有发现明显的数据问题或规律。")
        return
    for f in findings:
        icon = SEVERITY.get(f.get("severity", "low"), "🔵")
        with st.container(border=True):
            left, right = st.columns([5, 1])
            left.markdown(f"{icon} **{f['title']}**")
            right.caption(f"参考分 {f['score']}")
            st.write(f["detail"])
            if f.get("columns"):
                st.caption("涉及字段：" + "、".join(f["columns"]))


def render_profile(profile: dict) -> None:
    st.markdown("##### 自动识别结果")
    for line in profile.get("summary", []):
        st.markdown(f"- {line}")

    issues = (profile.get("quality") or {}).get("issues", [])
    if issues:
        st.markdown("##### 数据质量问题")
        for issue in issues:
            icon = SEVERITY.get(issue.get("severity", "low"), "🔵")
            st.markdown(f"{icon} **{issue['title']}** — {issue['detail']}")

    st.markdown("##### 字段画像")
    if profile.get("columns"):
        table(profile_frame(profile))

    load = profile.get("load") or {}
    if load:
        bits = []
        if load.get("encoding"):
            bits.append(f"编码 {load['encoding']}")
        if load.get("delimiter"):
            bits.append(f"分隔符 {load['delimiter']!r}")
        if load.get("sheet"):
            bits.append(f"工作表 {load['sheet']}")
        if bits:
            st.caption("读取信息：" + "｜".join(bits))
        for warning in load.get("warnings") or []:
            st.warning(warning, icon="⚠️")


def render_insights(insights: dict) -> None:
    if not insights:
        st.info("暂无结论。")
        return

    if insights.get("engine") == "llm":
        st.caption(f"由 {insights.get('model', '大模型')} 生成")
    elif insights.get("reason"):
        st.caption(insights["reason"])

    with st.container(border=True):
        st.markdown("##### 整体结论")
        st.write(insights.get("summary", "—"))

    findings = insights.get("key_findings") or []
    if findings:
        st.markdown("##### 关键发现")
        for item in findings:
            st.markdown(f"- **{item['title']}**：{item['detail']}")

    left, right = st.columns(2)
    with left:
        st.markdown("##### 建议动作")
        suggestions = insights.get("suggestions") or []
        for s in suggestions:
            st.markdown(f"- {s}")
        if not suggestions:
            st.caption("—")
    with right:
        st.markdown("##### 注意事项")
        caveats = insights.get("caveats") or []
        for c in caveats:
            st.markdown(f"- {c}")
        if not caveats:
            st.caption("—")


def render_preview(file_id: str, key_prefix: str = "p") -> None:
    if not file_id:
        return
    try:
        data = api.preview_file(file_id, rows=100)
    except api.ApiError as exc:
        st.error(str(exc))
        return
    st.caption(
        f"共 {data['total_rows']:,} 行 × {data['total_cols']} 列，下面展示前 {len(data['rows'])} 行"
    )
    if data.get("rows"):
        table(pd.DataFrame(data["rows"]))
    for warning in data.get("warnings") or []:
        st.warning(warning, icon="⚠️")
