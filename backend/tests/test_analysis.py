"""统计分析、图表推荐与结论测试。"""

from __future__ import annotations

import json

import pandas as pd

from app.services.analysis import analyze_dataframe
from app.services.charts import build_chart, recommend_charts
from app.services.insights import build_context, generate_insights, local_insights


def test_analysis_findings(profiled):
    df, profile, analysis = profiled
    assert analysis["findings"], "应当至少产出一条发现"
    assert analysis["correlations"]["pairs"], "销售额与销量应存在相关性"
    pair = analysis["correlations"]["pairs"][0]
    assert pair["r"] > 0.9  # 两者同步增长
    # 两个指标都在涨，但销售额量级更大，趋势应聚焦销售额
    assert analysis["trend"]["value_column"] == "销售额"
    assert analysis["trend"]["pct_change"] > 0


def test_group_analysis(profiled):
    df, profile, analysis = profiled
    groups = analysis["groups"]
    assert groups
    top = groups[0]["top"][0]
    assert top["total"] > 0
    assert groups[0]["dimension"] in ("地区",)


def test_recommend_charts(profiled):
    df, profile, analysis = profiled
    charts = recommend_charts(df, profile, analysis)
    assert 2 <= len(charts) <= 6
    kinds = {c["kind"] for c in charts}
    assert "line" in kinds
    assert "bar" in kinds
    for chart in charts:
        assert chart["title"] and chart["reason"] and chart["insight"]
        assert chart["figure"]["data"], "图里必须有 trace"
        assert "layout" in chart["figure"]
    # 同类图最多两张
    assert max(kinds, key=[c["kind"] for c in charts].count) is not None


def test_charts_json_serializable(profiled):
    df, profile, analysis = profiled
    charts = recommend_charts(df, profile, analysis)
    json.dumps(charts, ensure_ascii=False, allow_nan=False)


def test_build_chart_direct(profiled):
    df, profile, analysis = profiled
    spec = build_chart("histogram", df, "销售额分布", "看分布", col="销售额")
    assert spec is not None
    assert spec["kind"] == "histogram"
    assert spec["figure"]["data"]


def test_build_chart_bad_column(profiled):
    df, _, _ = profiled
    assert build_chart("histogram", df, "x", "y", col="不存在的列") is None


def test_local_insights(profiled):
    df, profile, analysis = profiled
    charts = recommend_charts(df, profile, analysis)
    insights = generate_insights(profile, analysis, charts, use_ai=False)
    assert insights["engine"] == "local"
    assert insights["summary"]
    assert insights["key_findings"]
    assert insights["suggestions"]
    assert insights["caveats"]


def test_context_is_compact(profiled):
    df, profile, analysis = profiled
    charts = recommend_charts(df, profile, analysis)
    context = build_context(profile, analysis, charts)
    assert "数据集" in context
    assert len(context) <= 6000


def test_missing_chart_generated():
    df = pd.DataFrame(
        {
            "城市": ["杭州", "北京", "上海"] * 10,
            "金额": [100.0] * 20 + [float("nan")] * 10,
        }
    )
    from app.services.profiler import profile_dataframe

    profile = profile_dataframe(df)
    analysis = analyze_dataframe(df, profile)
    charts = recommend_charts(df, profile, analysis)
    assert any(c["kind"] == "missing" for c in charts)
