"""数据读取与类型推断测试。"""

from __future__ import annotations

import pandas as pd

from app.services.loader import detect_delimiter, detect_encoding, load_dataframe


def test_detect_encoding_gbk():
    raw = "日期,地区\n2024-01-01,华东\n".encode("gbk")
    assert detect_encoding(raw) in ("gbk", "gb18030", "utf-8")


def test_detect_delimiter_semicolon():
    sample = "日期;地区;金额\n2024-01-01;华东;100\n2024-01-02;华北;200\n"
    assert detect_delimiter(sample) == ";"


def test_load_gbk_semicolon(tmp_path):
    text = "日期;地区;金额\n2024-01-01;华东;100\n2024-01-02;华北;200\n2024-01-03;华南;300\n"
    path = tmp_path / "gbk.csv"
    path.write_bytes(text.encode("gbk"))

    result = load_dataframe(path)
    assert result.delimiter == ";"
    assert result.df.shape == (3, 3)
    assert list(result.df.columns) == ["日期", "地区", "金额"]
    assert str(result.df["日期"].dtype).startswith("datetime64")


def test_numeric_strings_and_ids(tmp_path):
    df = pd.DataFrame(
        {
            "编号": ["001", "002", "003"],
            "金额": ["1,200", "3,400", "5,600"],
            "比例": ["12%", "35%", "48%"],
        }
    )
    path = tmp_path / "mixed.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")

    result = load_dataframe(path)
    # 前导零编号必须保留为文本，不能被转成 1/2/3
    assert result.df["编号"].tolist() == ["001", "002", "003"]
    assert result.df["金额"].tolist() == [1200, 3400, 5600]
    assert result.df["比例"].tolist() == [12, 35, 48]


def test_blank_lines_and_unnamed_columns(tmp_path):
    text = "列1,列2\n\n1,2\n3,4\n"
    path = tmp_path / "blank.csv"
    path.write_text(text, encoding="utf-8")
    result = load_dataframe(path)
    assert result.df.shape == (2, 2)
    assert result.df.isna().sum().sum() == 0


def test_excel_loads_largest_sheet(tmp_path, sales_df):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        sales_df.head(3).to_excel(writer, sheet_name="小表", index=False)
        sales_df.to_excel(writer, sheet_name="大表", index=False)

    result = load_dataframe(path)
    assert result.sheet_name == "大表"
    assert result.df.shape[0] == len(sales_df)
    assert set(result.sheet_names) == {"小表", "大表"}


def test_unsupported_extension(tmp_path):
    path = tmp_path / "note.docx"
    path.write_bytes(b"not a table")
    try:
        load_dataframe(path)
    except RuntimeError as exc:
        assert "不支持" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("应当拒绝不支持的格式")
