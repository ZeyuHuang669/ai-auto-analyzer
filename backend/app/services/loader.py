"""文件读取：CSV / Excel / JSON，自动识别编码、分隔符、表头、数据类型。"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SUPPORTED_CSV = {".csv", ".tsv", ".txt"}
SUPPORTED_EXCEL = {".xlsx", ".xlsm", ".xls"}
SUPPORTED_JSON = {".json", ".jsonl", ".ndjson"}
SUPPORTED_EXT = SUPPORTED_CSV | SUPPORTED_EXCEL | SUPPORTED_JSON

_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "latin-1")
_DELIMITERS = (",", ";", "\t", "|")


@dataclass
class LoadResult:
    df: pd.DataFrame
    encoding: str = "utf-8"
    delimiter: str | None = None
    sheet_name: str | None = None
    sheet_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    header_row: int = 0
    type_changes: dict[str, str] = field(default_factory=dict)


def _read_text_sample(path: Path, size: int = 262_144) -> bytes:
    with path.open("rb") as fh:
        return fh.read(size)


def detect_encoding(raw: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample[:64_000], delimiters="".join(_DELIMITERS))
        return dialect.delimiter
    except Exception:
        pass
    lines = [ln for ln in sample.splitlines() if ln.strip()][:30]
    best, best_score = ",", -1.0
    for delim in _DELIMITERS:
        counts = [ln.count(delim) for ln in lines]
        if not counts or max(counts) == 0:
            continue
        # 分隔符在每行出现次数越稳定，越可能是真正的分隔符
        score = float(np.mean(counts)) - float(np.std(counts)) * 0.5
        if score > best_score:
            best, best_score = delim, score
    return best


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    names: list[str] = []
    seen: dict[str, int] = {}
    for i, col in enumerate(df.columns):
        name = str(col).strip().replace("\n", " ").replace("\r", " ")
        if not name or name.lower().startswith("unnamed"):
            name = f"列{i + 1}"
        name = " ".join(name.split())
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        names.append(name)
    df = df.copy()
    df.columns = names
    return df


def _trim_empty(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.dropna(how="all", axis=0)
    # 只删除全空且列名是自动生成的列，避免删掉用户有意义的空列
    keep = []
    for i, col in enumerate(df.columns):
        s = df[col]
        if s.isna().all() and str(col).startswith("列") and str(col)[1:].isdigit():
            continue
        keep.append(col)
    return df[keep] if keep else df


def _read_csv(path: Path, max_rows: int | None) -> LoadResult:
    raw = _read_text_sample(path)
    encoding = detect_encoding(raw)
    sample = raw.decode(encoding, errors="replace")
    delimiter = detect_delimiter(sample)
    warnings: list[str] = []

    def _load(delim: str) -> pd.DataFrame:
        # 先全部按字符串读入，交给 infer_types 统一判断类型，
        # 否则 "001" 会被 pandas 直接变成 1，丢掉编号的前导零
        return pd.read_csv(
            path,
            sep=delim,
            encoding=encoding,
            nrows=max_rows,
            low_memory=False,
            skip_blank_lines=True,
            engine="c",
            dtype=str,
        )

    df = _load(delimiter)
    # 只解析出 1 列时说明分隔符猜错了，换一个再试
    if df.shape[1] <= 1:
        best_df, best_delim = df, delimiter
        for delim in _DELIMITERS:
            if delim == delimiter:
                continue
            try:
                cand = _load(delim)
            except Exception:
                continue
            if cand.shape[1] > best_df.shape[1]:
                best_df, best_delim = cand, delim
        if best_df.shape[1] > df.shape[1]:
            df, delimiter = best_df, best_delim
            warnings.append(f"分隔符自动修正为 {delimiter!r}")

    if df.shape[1] <= 1:
        warnings.append("只解析出 1 列，文件可能不是标准表格或用到了未知分隔符")

    return LoadResult(df=df, encoding=encoding, delimiter=delimiter, warnings=warnings)


def _detect_header_row(raw_df: pd.DataFrame, scan: int = 8) -> int:
    """Excel 常带标题行/说明行，找出最像表头的那一行。"""
    best_row, best_score = 0, -1.0
    for idx in range(min(scan, len(raw_df))):
        row = raw_df.iloc[idx]
        non_null = row.notna().sum()
        if non_null < 2:
            continue
        textish = sum(1 for v in row if isinstance(v, str) and v.strip())
        uniq = row.nunique(dropna=True)
        score = textish * 2 + uniq + non_null * 0.5
        if score > best_score:
            best_row, best_score = idx, score
    return best_row


def _read_excel(path: Path, sheet_name: str | None, max_rows: int | None) -> LoadResult:
    warnings: list[str] = []
    try:
        sheets = pd.read_excel(path, sheet_name=None, nrows=max_rows)
    except ImportError as exc:  # .xls 需要 xlrd
        raise RuntimeError(
            "读取 .xls 需要先安装 xlrd：pip install xlrd（或把文件另存为 .xlsx）"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Excel 读取失败：{exc}") from exc

    sheet_names = list(sheets.keys())
    if not sheet_names:
        raise RuntimeError("Excel 文件里没有工作表")

    if sheet_name and sheet_name in sheets:
        chosen = sheet_name
    else:
        if sheet_name:
            warnings.append(f"未找到工作表 {sheet_name}，已改用数据量最大的工作表")
        chosen = max(sheets, key=lambda k: sheets[k].shape[0] * max(1, sheets[k].shape[1]))

    raw_df = sheets[chosen]
    header_row = 0
    if raw_df.shape[1] >= 2:
        unnamed = sum(
            1 for c in raw_df.columns if str(c).strip().lower().startswith("unnamed")
        )
        if unnamed >= max(1, raw_df.shape[1] // 2):
            header_row = _detect_header_row(raw_df)
            warnings.append(f"检测到表头在第 {header_row + 1} 行")

    if header_row:
        raw_df = pd.read_excel(
            path, sheet_name=chosen, header=header_row, nrows=max_rows
        )

    if len(sheet_names) > 1:
        warnings.append(f"文件包含 {len(sheet_names)} 个工作表，已选用「{chosen}」")

    return LoadResult(
        df=raw_df,
        sheet_name=chosen,
        sheet_names=sheet_names,
        header_row=header_row,
        warnings=warnings,
    )


def _read_json(path: Path, max_rows: int | None) -> LoadResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    warnings: list[str] = []
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        # JSONL / NDJSON
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        payload = rows
        warnings.append("按 JSON Lines 格式解析")

    if isinstance(payload, dict):
        # 常见结构：{"data": [...]} / {"items": [...]}
        list_keys = [k for k, v in payload.items() if isinstance(v, list) and v]
        if list_keys:
            key = max(list_keys, key=lambda k: len(payload[k]))
            payload = payload[key]
            warnings.append(f"从字段「{key}」提取记录列表")
        else:
            payload = [payload]

    df = pd.DataFrame(payload)
    if max_rows:
        df = df.head(max_rows)
    return LoadResult(df=df, warnings=warnings)


def load_dataframe(
    path: str | Path,
    sheet_name: str | None = None,
    max_rows: int | None = None,
) -> LoadResult:
    """按扩展名读取文件，返回 DataFrame 与读取元信息。"""
    path = Path(path)
    ext = path.suffix.lower()
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    if ext in SUPPORTED_CSV:
        result = _read_csv(path, max_rows)
    elif ext in SUPPORTED_EXCEL:
        result = _read_excel(path, sheet_name, max_rows)
    elif ext in SUPPORTED_JSON:
        result = _read_json(path, max_rows)
    else:
        raise RuntimeError(
            f"暂不支持 {ext} 格式，支持：{', '.join(sorted(SUPPORTED_EXT))}"
        )

    df = result.df
    if df.empty:
        raise RuntimeError("文件里没有读到任何数据行")

    df = _normalize_columns(df)
    df = _trim_empty(df)
    if df.empty:
        raise RuntimeError("剔除空行空列后没有剩余数据")

    df = infer_types(df)
    result.df = df
    return result


# --------------------------------------------------------------------------- #
# 类型推断：把所有列尽量转成 datetime / numeric / bool，无法转换的保留文本
# --------------------------------------------------------------------------- #

_TRUE_WORDS = {"true", "yes", "y", "是", "对", "真", "1"}
_FALSE_WORDS = {"false", "no", "n", "否", "错", "假", "0"}


def _is_text_series(s: pd.Series) -> bool:
    if pd.api.types.is_string_dtype(s) or s.dtype == object:
        return True
    return False


def _looks_like_id(values: list[str]) -> bool:
    if not values:
        return False
    if any(v.startswith("0") and v.isdigit() and len(v) > 1 for v in values):
        return True
    lens = {len(v) for v in values}
    return len(lens) == 1 and len(values[0]) >= 12 and all(v.isdigit() for v in values)


def _try_numeric(s: pd.Series) -> pd.Series | None:
    non_null = s.dropna().astype(str).str.strip()
    if non_null.empty:
        return None
    # 去掉千分位和百分号/货币符号再试
    cleaned = non_null.str.replace(r"[,\s￥$€¥]", "", regex=True).str.replace(
        r"%$", "", regex=True
    )
    if _looks_like_id(cleaned.head(50).tolist()):
        return None
    converted = pd.to_numeric(cleaned, errors="coerce")
    ok_ratio = float(converted.notna().mean())
    if ok_ratio < 0.95:
        return None
    return converted.reindex(s.index)


def _try_datetime(s: pd.Series) -> pd.Series | None:
    non_null = s.dropna().astype(str).str.strip()
    if non_null.empty or len(non_null) < 3:
        return None
    sample = non_null.head(200)
    # 纯数字（尤其 8 位以内）不当日期，避免把 20240101 之外的编码误判
    if sample.str.fullmatch(r"\d{1,11}").all():
        return None
    try:
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    except Exception:
        return None
    ok_ratio = float(parsed.notna().mean())
    if ok_ratio < 0.9:
        return None
    full = pd.to_datetime(s, errors="coerce", format="mixed")
    return full


def _try_bool(s: pd.Series) -> pd.Series | None:
    non_null = s.dropna()
    if non_null.empty:
        return None
    uniques = {str(v).strip().lower() for v in non_null.unique()[:10]}
    if not uniques.issubset(_TRUE_WORDS | _FALSE_WORDS):
        return None
    if len(uniques) > 2:
        return None
    mapped = s.astype(str).str.strip().str.lower().map(
        lambda v: True if v in _TRUE_WORDS else (False if v in _FALSE_WORDS else None)
    )
    return mapped.astype("boolean")


def infer_types(df: pd.DataFrame) -> pd.DataFrame:
    """尽量把文本列转成数值 / 日期 / 布尔，并记录转换结果。"""
    df = df.copy()
    for col in df.columns:
        s = df[col]
        if not _is_text_series(s):
            continue
        name = str(col).lower()
        non_null = s.dropna()
        if non_null.empty:
            continue

        # 1) 布尔
        as_bool = _try_bool(s)
        if as_bool is not None and as_bool.notna().sum() >= len(non_null) * 0.95:
            df[col] = as_bool
            continue

        # 2) 名称里带日期线索，优先按日期解析
        date_hint = any(
            k in name
            for k in ("date", "time", "日期", "时间", "年月", "月份", "_dt", "timestamp")
        )
        if date_hint:
            as_dt = _try_datetime(s)
            if as_dt is not None:
                df[col] = as_dt
                continue

        # 3) 数值
        as_num = _try_numeric(s)
        if as_num is not None:
            df[col] = as_num
            continue

        # 4) 日期（无名称线索时，要求格式非常一致）
        as_dt = _try_datetime(s)
        if as_dt is not None:
            df[col] = as_dt
            continue

    return df
