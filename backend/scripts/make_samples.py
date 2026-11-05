"""生成示例数据：销售明细 CSV + 员工信息 Excel，用于验证整条流水线。"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import SAMPLE_DIR

random.seed(7)
rng = np.random.default_rng(7)


def make_sales(rows: int = 900) -> pd.DataFrame:
    regions = ["华东", "华北", "华南", "西南", "东北"]
    categories = ["数码", "家电", "服饰", "食品", "家居"]
    channels = ["线上", "线下", "分销"]

    dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    picked = rng.choice(dates, size=rows)

    region = rng.choice(regions, size=rows, p=[0.34, 0.22, 0.24, 0.12, 0.08])
    category = rng.choice(categories, size=rows)
    channel = rng.choice(channels, size=rows, p=[0.55, 0.3, 0.15])

    month = pd.DatetimeIndex(picked).month.to_numpy()
    season = 1 + 0.35 * np.sin((month - 3) / 12 * 2 * np.pi)  # 春夏旺季
    base = rng.normal(1200, 380, size=rows).clip(80, None)
    price_hint = np.select(
        [category == "数码", category == "家电", category == "服饰",
         category == "食品", category == "家居"],
        [3.2, 2.4, 0.6, 0.25, 1.1],
    )
    amount = (base * season * price_hint * rng.uniform(0.75, 1.4, size=rows)).round(2)
    qty = (amount / (base * price_hint) * rng.uniform(1, 4, size=rows)).round().astype(int) + 1

    df = pd.DataFrame(
        {
            "订单日期": pd.DatetimeIndex(picked).strftime("%Y-%m-%d"),
            "地区": region,
            "品类": category,
            "渠道": channel,
            "销售额": amount,
            "销量": qty,
            "折扣率": np.round(rng.uniform(0, 0.35, size=rows), 2),
            "客户评分": np.round(rng.normal(4.2, 0.45, size=rows).clip(1, 5), 1),
            "是否退货": rng.choice(["是", "否"], size=rows, p=[0.07, 0.93]),
        }
    )
    df["毛利率"] = (df["销售额"] * rng.uniform(0.12, 0.42, size=rows)).round(2)

    # 人为制造一些问题，验证缺失/重复/异常值检测
    idx = rng.choice(df.index, size=int(rows * 0.06), replace=False)
    df.loc[idx[:30], "客户评分"] = np.nan
    df.loc[idx[30:45], "毛利率"] = np.nan
    df.loc[idx[45:50], "销售额"] = df.loc[idx[45:50], "销售额"] * 45  # 极端值

    dup = df.sample(6, random_state=1)
    df = pd.concat([df, dup], ignore_index=True)
    return df


def make_employees(rows: int = 260) -> pd.DataFrame:
    departments = ["研发", "销售", "市场", "运营", "职能"]
    levels = ["P4", "P5", "P6", "P7"]
    cities = ["杭州", "北京", "上海", "成都", "深圳"]

    dept = rng.choice(departments, size=rows, p=[0.38, 0.24, 0.14, 0.16, 0.08])
    level = rng.choice(levels, size=rows, p=[0.34, 0.38, 0.2, 0.08])
    city = rng.choice(cities, size=rows)

    base = np.select(
        [dept == "研发", dept == "销售", dept == "市场", dept == "运营", dept == "职能"],
        [1.25, 1.05, 0.95, 0.9, 0.85],
    )
    level_mult = np.select(
        [level == "P4", level == "P5", level == "P6", level == "P7"],
        [1.0, 1.35, 1.85, 2.6],
    )
    salary = (9000 * base * level_mult * rng.uniform(0.88, 1.18, size=rows)).round(-2)
    tenure = rng.gamma(2.2, 1.4, size=rows).round(1).clip(0.2, 15)
    performance = np.clip(
        rng.normal(3.6, 0.55, size=rows) + (tenure - 3) * 0.03, 1, 5
    ).round(1)
    age = (salary / 1000 * 0.9 + rng.normal(18, 4, size=rows)).round(0).clip(22, 58)

    df = pd.DataFrame(
        {
            "员工编号": [f"E{1000 + i:04d}" for i in range(rows)],
            "部门": dept,
            "职级": level,
            "城市": city,
            "入职日期": pd.to_datetime("2018-01-01")
            + pd.to_timedelta(rng.integers(0, 2400, size=rows), unit="D"),
            "司龄": tenure,
            "月薪": salary,
            "绩效评分": performance,
            "年龄": age,
        }
    )
    df.loc[rng.choice(df.index, 18, replace=False), "绩效评分"] = np.nan
    return df


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    sales = make_sales()
    sales_path = SAMPLE_DIR / "sales_2024.csv"
    sales.to_csv(sales_path, index=False, encoding="utf-8-sig")

    employees = make_employees()
    emp_path = SAMPLE_DIR / "employees.xlsx"
    with pd.ExcelWriter(emp_path, engine="openpyxl") as writer:
        employees.to_excel(writer, sheet_name="员工花名册", index=False)
        employees.head(50).to_excel(writer, sheet_name="抽样", index=False)

    print(f"已生成 {sales_path}（{len(sales)} 行）")
    print(f"已生成 {emp_path}（{len(employees)} 行，2 个工作表）")


if __name__ == "__main__":
    main()
