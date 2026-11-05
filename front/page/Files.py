import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from lib import api, ui

st.title("📁 文件管理")
st.caption("支持 CSV / TSV / Excel / JSON，上传后自动识别编码、分隔符、表头与字段类型。")

# ---------------------------------------------------------------- 上传
with st.container(border=True):
    st.markdown("##### 上传文件")
    uploaded = st.file_uploader(
        "选择文件（可多选）",
        type=["csv", "tsv", "txt", "xlsx", "xlsm", "xls", "json", "jsonl"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    sheet = st.text_input(
        "指定工作表（可选，仅 Excel）",
        placeholder="留空则自动选择数据量最大的工作表",
    )
    if uploaded and st.button("上传并解析", type="primary", icon="📤"):
        payloads = [
            (f.name, f.getvalue(), f.type or "application/octet-stream") for f in uploaded
        ]
        with st.spinner("正在上传并识别数据…"):
            try:
                result = api.upload_files(payloads, sheet=sheet.strip() or None)
            except api.ApiError as exc:
                st.error(str(exc))
                result = None

        if result:
            for item in result.get("files", []):
                if item.get("duplicated"):
                    st.info(f"「{item['name']}」已存在，直接复用")
                elif item.get("error"):
                    st.error(f"「{item['name']}」解析失败：{item['error']}")
                else:
                    preview = item.get("profile_preview") or {}
                    st.success(
                        f"「{item['name']}」上传成功：{item['rows']:,} 行 × {item['cols']} 列"
                        f"｜识别为 {preview.get('kind', '表格')}"
                        f"｜质量 {preview.get('quality', {}).get('score', '—')}"
                    )
                    for warning in item.get("warnings") or []:
                        st.warning(warning, icon="⚠️")
            st.rerun()

# ---------------------------------------------------------------- 文件列表
try:
    data = api.list_files(limit=100)
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

files = data.get("items", [])
if not files:
    ui.empty_state(
        "还没有文件",
        "先用上面的上传框传一个 CSV 或 Excel，系统会自动识别数据并准备分析。",
    )
    st.stop()

st.markdown("##### 已上传文件")
ui.table(
    pd.DataFrame(
        [
            {
                "文件名": f["name"],
                "行数": f"{f['rows']:,}",
                "列数": f["cols"],
                "状态": ui.STATUS_TEXT.get(f["status"], f["status"]),
                "分析次数": f.get("run_count", 0),
                "大小": ui.fmt_bytes(f["size_bytes"]),
                "上传时间": ui.fmt_time(f.get("created_at"), "%Y-%m-%d %H:%M"),
            }
            for f in files
        ]
    )
)

# ---------------------------------------------------------------- 操作区
id_to_file = {f["id"]: f for f in files}
selected_id = st.selectbox(
    "选择要操作的文件",
    options=list(id_to_file.keys()),
    format_func=lambda i: f"{id_to_file[i]['name']}（{id_to_file[i]['rows']:,} 行）",
)

use_ai = st.checkbox("分析时用 AI 生成结论", value=True)

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    preview_clicked = st.button("👀 预览数据", width="stretch")
with col2:
    analyze_clicked = st.button("🚀 开始自动分析", type="primary", width="stretch")
with col3:
    confirm = st.session_state.get("confirm_delete") == selected_id
    if st.button("🗑️ 确认删除" if confirm else "🗑️ 删除文件", width="stretch"):
        if confirm:
            try:
                api.delete_file(selected_id)
                st.session_state.pop("confirm_delete", None)
                st.success("已删除")
                st.rerun()
            except api.ApiError as exc:
                st.error(str(exc))
        else:
            st.session_state["confirm_delete"] = selected_id
            st.warning("再点一次确认删除（会同时删除该文件的分析历史）")

if preview_clicked:
    st.session_state["preview_file_id"] = selected_id

if st.session_state.get("preview_file_id"):
    pid = st.session_state["preview_file_id"]
    try:
        pv = api.preview_file(pid, rows=30)
    except api.ApiError as exc:
        st.error(str(exc))
    else:
        st.markdown(f"##### 数据预览：{pv['name']}")
        st.caption(
            f"{pv['total_rows']:,} 行 × {pv['total_cols']} 列"
            + (f"｜工作表 {pv['sheet_name']}" if pv.get("sheet_name") else "")
        )
        ui.table(pd.DataFrame(pv["rows"]))
        for warning in pv.get("warnings") or []:
            st.warning(warning, icon="⚠️")

if analyze_clicked:
    with st.spinner("正在自动识别 → 统计分析 → 推荐图表 → 生成结论…"):
        try:
            run = api.run_analysis(selected_id, use_ai=use_ai, force=True)
        except api.ApiError as exc:
            st.error(str(exc))
        else:
            st.session_state["current_run"] = run
            st.session_state["current_file_name"] = id_to_file[selected_id]["name"]
            st.switch_page("page/DataAnalysis.py")
