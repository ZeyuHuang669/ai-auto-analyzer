"""AI 生成分析结论：优先走大模型，失败时用规则结论兜底，保证永远有输出。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.llm import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一名严谨的中文数据分析师。你会收到一份数据集的自动分析结果（字段画像、统计发现、相关性、趋势、分组对比、图表解读）。
请基于这些事实写一份简短结论，要求：
1. 只使用给定的事实和数字，禁止编造列名、数值或结论；
2. 语言简洁专业，面向不懂技术的业务同事；
3. 严格输出 JSON，不要输出任何多余文字。

JSON 结构：
{
  "summary": "80 字以内的整体结论",
  "key_findings": [{"title": "不超过 16 字", "detail": "一两句话，尽量带数字"}],
  "suggestions": ["可执行建议，2-4 条"],
  "caveats": ["数据局限或注意事项，1-3 条"]
}"""


def _col_line(col: dict) -> str:
    parts = [f"{col['name']}（{col['role_label']}）"]
    st = col.get("stats")
    if st:
        parts.append(
            f"均值{st.get('mean')}，中位数{st.get('median')}，范围{st.get('min')}~{st.get('max')}"
        )
    top = col.get("top_values")
    if top:
        parts.append(
            "TOP:" + "、".join(f"{t['value']}({t['count']})" for t in top[:3])
        )
    if col.get("missing_ratio"):
        parts.append(f"缺失{col['missing_ratio']:.1%}")
    return "；".join(parts)


def build_context(profile: dict, analysis: dict, charts: list[dict]) -> str:
    """压缩成给模型看的纯文本事实（控制在 6000 字符以内）。"""
    lines: list[str] = []
    lines.append(
        f"数据集：{profile.get('source') or '未命名'}，{profile['rows']} 行 × {profile['cols']} 列，"
        f"类型：{profile['kind']}，质量分 {profile['quality']['score']}/{profile['quality']['grade']}"
    )
    lines.append(
        f"缺失率 {profile['missing_ratio']:.2%}，重复行 {profile['duplicate_rows']} 条"
    )
    lines.append("字段：")
    for col in profile["columns"][:25]:
        lines.append("  - " + _col_line(col))

    if analysis.get("correlations", {}).get("pairs"):
        lines.append("相关性（|r| 从高到低）：")
        for p in analysis["correlations"]["pairs"][:5]:
            lines.append(f"  - {p['a']} × {p['b']}: r={p['r']}（{p['strength']}{p['direction']}）")

    trend = analysis.get("trend")
    if trend:
        lines.append(
            f"趋势：{trend['value_column']} 按{trend['freq_label']}从 {trend['first']:.2f} 到 "
            f"{trend['last']:.2f}，变化 {trend['pct_change']}%，R²={trend['r2']}"
        )

    for g in analysis.get("groups", [])[:2]:
        top = "、".join(f"{t['group']}={t['total']:.2f}" for t in g["top"][:4])
        lines.append(f"分组（按 {g['dimension']} 汇总 {g['measure']}）：{top}")

    if analysis.get("findings"):
        lines.append("已有发现：")
        for f in analysis["findings"][:8]:
            lines.append(f"  - {f['title']}：{f['detail']}")

    if charts:
        lines.append("已生成的图表：")
        for c in charts[:6]:
            lines.append(f"  - {c['title']}：{c['insight']}")

    text = "\n".join(lines)
    return text[:6000]


def local_insights(profile: dict, analysis: dict, charts: list[dict]) -> dict:
    """没有可用模型时的规则版结论。"""
    findings = analysis.get("findings", [])
    quality = profile["quality"]

    summary = (
        f"这份数据共 {profile['rows']:,} 行 × {profile['cols']} 列，属于{profile['kind']}，"
        f"数据质量 {quality['score']} 分（{quality['grade']}）。"
    )
    if findings:
        summary += "最值得关注的是：" + findings[0]["title"] + "。"
    elif charts:
        summary += charts[0]["insight"] + "。"

    key_findings = [
        {"title": f["title"], "detail": f["detail"]} for f in findings[:5]
    ]
    if not key_findings and charts:
        key_findings = [{"title": c["title"], "detail": c["insight"]} for c in charts[:3]]

    suggestions: list[str] = []
    kinds = {f["kind"] for f in findings}
    if "missing" in kinds:
        suggestions.append("先处理缺失率高的字段（填补或剔除），再重跑分组统计，避免样本偏差")
    if "duplicate" in kinds:
        suggestions.append("分析前先按业务主键去重，否则求和类指标会被高估")
    if "concentration" in kinds:
        suggestions.append("头部集中明显，建议把头部与长尾拆开看，分别制定策略")
    if "trend" in kinds:
        suggestions.append("对趋势做同比/环比拆解，确认是季节性还是结构性变化")
    if "correlation" in kinds:
        suggestions.append("相关字段可以做交叉分析或简单回归，但不要直接当成因果关系")
    if "outlier" in kinds:
        suggestions.append("核对异常值是否为录入错误；确认无误后可单独分析极端样本")
    if not suggestions:
        suggestions.append("按核心指标做时间对比，并固定每周复跑一次分析，跟踪变化")

    caveats: list[str] = []
    if profile["rows"] < 100:
        caveats.append(f"样本仅 {profile['rows']} 行，统计结论的稳定性有限")
    if profile["missing_ratio"] > 0.05:
        caveats.append("数据存在缺失，缺失可能不是随机的，结论会有偏差")
    if quality["grade"] in ("C", "D"):
        caveats.append("整体数据质量偏低，建议先做数据清洗再下结论")
    caveats.append("相关关系不等于因果关系，业务决策前需结合实际情况验证")

    return {
        "summary": summary,
        "key_findings": key_findings,
        "suggestions": suggestions[:4],
        "caveats": caveats[:3],
        "engine": "local",
        "model": "",
    }


def _sanitize(data: dict, fallback: dict) -> dict:
    out = dict(fallback)
    if isinstance(data.get("summary"), str) and data["summary"].strip():
        out["summary"] = data["summary"].strip()[:400]

    kf = data.get("key_findings")
    if isinstance(kf, list) and kf:
        cleaned = []
        for item in kf[:6]:
            if isinstance(item, dict) and item.get("title"):
                cleaned.append(
                    {
                        "title": str(item.get("title"))[:40],
                        "detail": str(item.get("detail") or "")[:300],
                    }
                )
        if cleaned:
            out["key_findings"] = cleaned

    for key, cap in (("suggestions", 4), ("caveats", 3)):
        val = data.get(key)
        if isinstance(val, list) and val:
            cleaned = [str(v)[:200] for v in val if str(v).strip()]
            if cleaned:
                out[key] = cleaned[:cap]
    return out


def generate_insights(
    profile: dict,
    analysis: dict,
    charts: list[dict],
    use_ai: bool = True,
) -> dict:
    fallback = local_insights(profile, analysis, charts)
    llm = get_llm()
    if not use_ai or not llm.available:
        fallback["engine"] = "local"
        fallback["reason"] = "未配置模型或未启用 AI，以下为规则生成的结论"
        return fallback

    user = build_context(profile, analysis, charts)
    try:
        data = llm.chat_json(SYSTEM_PROMPT, user, max_tokens=1200)
    except Exception as exc:  # pragma: no cover
        logger.warning("AI 结论生成失败：%s", exc)
        data = None

    if not data:
        fallback["reason"] = "模型调用失败，已回退规则结论"
        return fallback

    merged = _sanitize(data, fallback)
    merged["engine"] = "llm"
    merged["model"] = llm.model
    merged["reason"] = ""
    return merged
