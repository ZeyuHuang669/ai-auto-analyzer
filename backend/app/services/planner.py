"""AI Planner：把自然语言问题翻译成分析动作，执行后给出回答与配图。"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models import FileAsset
from app.services.analysis import analyze_dataframe
from app.services.charts import build_chart, recommend_charts
from app.services.llm import get_llm
from app.services.pipeline import load_frame
from app.services.profiler import profile_dataframe
from app.utils.json import to_python

logger = logging.getLogger(__name__)

INTENTS = {
    "trend": ("趋势", "变化", "走势", "增长", "下降", "上升", "时间", "月度", "环比", "同比", "trend"),
    "rank": ("排名", "最高", "最低", "最多", "最少", "top", "前几", "哪个", "对比", "比较", "差异"),
    "distribution": ("分布", "集中", "区间", "范围", "直方", "离散", "波动"),
    "correlation": ("相关", "关系", "影响", "关联"),
    "missing": ("缺失", "空值", "缺数据", "没有值"),
    "summary": ("总结", "概览", "介绍", "整体", "概况", "怎么样", "如何", "分析一下"),
}

PLAN_PROMPT = """你是数据分析 Planner。根据用户问题和字段列表，判断分析意图。
只输出 JSON：{"intent": "trend|rank|distribution|correlation|missing|summary", "column": "字段名或null", "measure": "数值字段或null"}
intent 含义：trend=看随时间变化；rank=分组对比/排名；distribution=看数值分布；correlation=看两个指标相关性；missing=看缺失；summary=整体概览。
字段必须从给定列表中原样选择，不确定就填 null。不要输出其他内容。"""

ANSWER_PROMPT = """你是数据分析助手。依据给出的事实回答问题，要求：
1. 先给结论，再给 2-3 条依据，每条尽量带具体数字；
2. 只能使用事实里出现的数字和字段名，禁止编造；
3. 中文，200 字以内，不要用 Markdown 标题。"""


def _heuristic_intent(question: str) -> str:
    q = question.lower()
    scores = {intent: 0 for intent in INTENTS}
    for intent, words in INTENTS.items():
        for w in words:
            if w in q:
                scores[intent] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "summary"


def _pick_column(question: str, columns: list[str]) -> str | None:
    """在问题里找被提到的字段（取最长匹配）。"""
    q = question.lower()
    matches = [c for c in columns if str(c).lower() in q]
    if matches:
        return max(matches, key=len)
    # 退一步：按字段名切词做部分匹配
    best, best_len = None, 0
    for col in columns:
        parts = [p for p in re.split(r"[\s_\-]+", str(col).lower()) if len(p) >= 2]
        for part in parts:
            if part in q and len(part) > best_len:
                best, best_len = col, len(part)
    return best


def _llm_intent(question: str, columns: list[str]) -> dict | None:
    llm = get_llm()
    if not llm.available:
        return None
    user = f"字段列表：{'、'.join(columns[:60])}\n问题：{question}"
    data = llm.chat_json(PLAN_PROMPT, user, max_tokens=200)
    if not isinstance(data, dict):
        return None
    if data.get("intent") not in INTENTS:
        return None
    return data


def _resolve_file(db: Session, question: str, file_id: str | None) -> FileAsset | None:
    if file_id:
        return db.get(FileAsset, file_id)
    files = (
        db.query(FileAsset)
        .filter(FileAsset.status != "failed")
        .order_by(FileAsset.created_at.desc())
        .all()
    )
    if not files:
        return None
    q = question.lower()
    for f in files:
        stem = Path(f.name).stem.lower()
        if stem and (stem in q or Path(f.name).name.lower() in q):
            return f
    return files[0]


def _facts_and_charts(
    df: pd.DataFrame,
    profile: dict,
    analysis: dict,
    intent: str,
    column: str | None,
    measure: str | None,
) -> tuple[list[str], list[dict], list[dict]]:
    """按意图算事实、配图，并记录执行步骤。"""
    measures = [c for c in profile["roles"]["measure"] if c in df.columns]
    times = [c for c in profile["roles"]["time"] if c in df.columns]
    dims = [c for c in profile["roles"]["dimension"] if c in df.columns]

    facts: list[str] = []
    charts: list[dict] = []
    steps: list[dict] = []

    m = measure if measure in measures else (column if column in measures else (measures[0] if measures else None))

    if intent == "trend" and times:
        tcol = column if column in times else times[0]
        mcol = m or (measures[0] if measures else None)
        if mcol:
            spec = build_chart(
                "line", df, f"{mcol} 随时间变化",
                f"问题关注趋势，用「{tcol}」作为时间轴、按周期汇总「{mcol}」", 
                time_col=tcol, value_col=mcol,
            )
            steps.append({"op": "trend", "args": {"time": tcol, "value": mcol}})
            if spec:
                charts.append(spec)
                facts.append(spec["insight"])

    elif intent == "rank" and dims:
        d = column if column in dims else dims[0]
        if m:
            spec = build_chart(
                "bar", df, f"各{d}的{m}对比",
                f"问题要求比较，用「{d}」分组统计「{m}」",
                dim=d, measure=m,
            )
            steps.append({"op": "group_compare", "args": {"dimension": d, "measure": m}})
            if spec:
                charts.append(spec)
                facts.append(spec["insight"])
                top = spec["data"][:3]
                facts.append(
                    "前三名：" + "、".join(f"{t['group']}({t['value']:,.2f})" for t in top)
                )

    elif intent == "distribution" and m:
        stats = next((x for x in analysis.get("measures", []) if x["column"] == m), None)
        spec = build_chart(
            "histogram", df, f"{m} 的分布",
            "问题关注分布形态，用直方图看集中区间与偏斜",
            col=m,
        )
        steps.append({"op": "distribution", "args": {"column": m}})
        if spec:
            charts.append(spec)
            facts.append(spec["insight"])
        if stats:
            facts.append(
                f"{m} 的均值 {stats['mean']:,.2f}，中位数 {stats['median']:,.2f}，"
                f"标准差 {stats['std']:,.2f}，偏度 {stats['skew']:.2f}，"
                f"最小值 {stats['min']:,.2f}，最大值 {stats['max']:,.2f}"
            )

    elif intent == "correlation":
        pairs = analysis.get("correlations", {}).get("pairs", [])
        if pairs:
            pair = pairs[0]
            spec = build_chart(
                "scatter", df, f"{pair['a']} 与 {pair['b']} 的关系",
                "问题关心相关性，用散点图看线性关系与离群点",
                x_col=pair["a"], y_col=pair["b"],
            )
            steps.append({"op": "correlation", "args": {"a": pair["a"], "b": pair["b"]}})
            if spec:
                charts.append(spec)
            for p in pairs[:3]:
                facts.append(
                    f"{p['a']} 与 {p['b']}：r={p['r']}（{p['strength']}{p['direction']}）"
                )

    elif intent == "missing":
        missing = sorted(
            [c for c in profile["columns"] if c["missing_ratio"] > 0],
            key=lambda c: c["missing_ratio"],
            reverse=True,
        )[:6]
        steps.append({"op": "missing_check", "args": {}})
        if missing:
            facts.append(
                "缺失最严重的字段："
                + "、".join(f"{c['name']}({c['missing_ratio']:.1%})" for c in missing)
            )
        else:
            facts.append("没有发现缺失值")
        for spec in recommend_charts(df, profile, analysis, limit=8):
            if spec["kind"] == "missing":
                charts.append(spec)
                break

    # summary 或没匹配到具体动作时，给整体事实
    if not facts:
        intent = "summary"
        facts.extend(profile.get("summary", [])[:3])
        for f in analysis.get("findings", [])[:4]:
            facts.append(f"{f['title']}：{f['detail']}")
        for spec in recommend_charts(df, profile, analysis, limit=2):
            charts.append(spec)
        steps.append({"op": "overview", "args": {}})

    # 补充一张与问题字段相关的图（避免只有文字）
    if len(charts) < 2:
        focus = {c for c in (column, measure, m) if c}
        extra = [
            s
            for s in recommend_charts(df, profile, analysis, limit=8)
            if focus & set(s["columns"]) and s["id"] not in {c["id"] for c in charts}
        ]
        if extra:
            charts.append(extra[0])

    return facts, charts[:3], steps


def run_planner(db: Session, question: str, file_id: str | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        raise ValueError("问题不能为空")

    file = _resolve_file(db, question, file_id)
    if file is None:
        return to_python(
            {
                "question": question,
                "error": "还没有上传任何文件，请先在「文件」页上传 CSV / Excel",
                "answer": "还没有可分析的数据，请先上传 CSV 或 Excel 文件。",
                "charts": [],
                "facts": [],
                "steps": [],
            }
        )

    df, load_meta = load_frame(file)
    profile = profile_dataframe(df, source_name=file.name)
    analysis = analyze_dataframe(df, profile)

    all_columns = [str(c) for c in df.columns]
    llm_plan = _llm_intent(question, all_columns)
    heuristic = _heuristic_intent(question)

    if llm_plan:
        intent = llm_plan["intent"]
        column = llm_plan.get("column")
        measure = llm_plan.get("measure")
        if column not in all_columns:
            column = None
        if measure not in all_columns:
            measure = None
    else:
        intent, column, measure = heuristic, None, None

    mentioned = _pick_column(question, all_columns)
    if column is None:
        column = mentioned
    if measure is None and mentioned in profile["roles"]["measure"]:
        measure = mentioned

    facts, charts, steps = _facts_and_charts(
        df, profile, analysis, intent, column, measure
    )

    engine = "local"
    answer = ""
    llm = get_llm()
    if llm.available:
        context = "\n".join(f"- {f}" for f in facts)
        chart_lines = "\n".join(f"- {c['title']}：{c['insight']}" for c in charts)
        user = (
            f"数据集：{file.name}（{profile['rows']} 行 × {profile['cols']} 列，{profile['kind']}）\n"
            f"问题：{question}\n\n事实：\n{context}\n\n图表结论：\n{chart_lines}"
        )
        answer = llm.chat(ANSWER_PROMPT, user, max_tokens=700) or ""
        if answer:
            engine = "llm"
    if not answer:
        answer = "\n".join(f"· {f}" for f in facts[:5])
        if charts:
            answer += f"\n\n已生成 {len(charts)} 张相关图表。"

    return to_python(
        {
            "question": question,
            "file_id": file.id,
            "file_name": file.name,
            "intent": intent,
            "plan_source": "llm" if llm_plan else "heuristic",
            "steps": steps,
            "facts": facts,
            "charts": charts,
            "answer": answer,
            "engine": engine,
            "load_warnings": load_meta.warnings,
        }
    )
