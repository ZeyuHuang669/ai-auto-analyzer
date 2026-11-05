"""字段识别与质量评分测试。"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.services.profiler import profile_dataframe
from app.utils.json import to_python


def test_roles_detected(sales_df):
    profile = profile_dataframe(sales_df, source_name="sales.csv")
    roles = profile["roles"]
    assert "日期" in roles["time"]
    assert "地区" in roles["dimension"]
    assert {"销售额", "销量", "评分"} <= set(roles["measure"])
    assert profile["kind"] == "时间序列"


def test_quality_flags_missing():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [None, None, 1, 2]})
    profile = profile_dataframe(df)
    issues = {i["kind"] for i in profile["quality"]["issues"]}
    assert "missing" in issues
    assert profile["missing_ratio"] > 0.2
    assert 0 <= profile["quality"]["score"] <= 100


def test_quality_flags_duplicates_and_constant():
    df = pd.DataFrame(
        {
            "id": [1, 1, 1],
            "value": [10, 10, 10],
            "const": ["x", "x", "x"],
        }
    )
    profile = profile_dataframe(df)
    issues = {i["kind"] for i in profile["quality"]["issues"]}
    assert "duplicate" in issues
    assert "constant" in issues
    assert profile["duplicate_rows"] == 2


def test_constant_and_id_columns():
    df = pd.DataFrame(
        {
            "订单号": [f"SO{i:06d}" for i in range(20)],
            "状态": ["完成"] * 20,
            "金额": [100 + i * 7 for i in range(20)],
        }
    )
    profile = profile_dataframe(df)
    by_name = {c["name"]: c for c in profile["columns"]}
    assert by_name["订单号"]["role"] == "id"
    assert by_name["状态"]["is_constant"] is True
    assert by_name["金额"]["role"] == "measure"


def test_time_range(sales_df):
    profile = profile_dataframe(sales_df)
    col = next(c for c in profile["columns"] if c["name"] == "日期")
    assert col["time"]["span_days"] == 59
    assert col["time"]["min"].startswith("2024-01-01")


def test_to_python_removes_nan():
    payload = {
        "a": float("nan"),
        "b": float("inf"),
        "c": np.int64(3),
        "d": np.float64(1.5),
        "e": pd.NaT,
        "f": pd.Timestamp("2024-01-01"),
        "g": np.array([1, 2]),
    }
    cleaned = to_python(payload)
    assert cleaned["a"] is None
    assert cleaned["b"] is None
    assert cleaned["c"] == 3 and isinstance(cleaned["c"], int)
    assert math.isclose(cleaned["d"], 1.5)
    assert cleaned["e"] is None
    assert cleaned["f"].startswith("2024-01-01")
    assert cleaned["g"] == [1, 2]
