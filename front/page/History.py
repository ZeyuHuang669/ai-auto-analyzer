import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from lib import api, ui

st.title("⬆️ 浏览历史")
st.caption("每次自动分析都会保存：字段画像、统计发现、图表与 AI 结论。")

try:
    files = api.list_files(limit=200).get("items", [])
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

if not files:
    ui.empty_state("还没有历史记录", "先上传并分析一个文件。", "page/Files.py", "去上传")
    st.stop()

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    id_to_name = {f["id"]: f["name"] for f in files}
    file_filter = st.selectbox(
        "按文件筛选",
        options=[""] + list(id_to_name.keys()),
        format_func=lambda x: "全部文件" if x == "" else id_to_name[x],
    )
with col2:
    status_filter = st.selectbox("按状态筛选", ["", "succeeded", "failed"],
                                format_func=lambda x: "全部状态" if x == "" else ui.STATUS_TEXT.get(x, x))
with col3:
    limit = st.selectbox("条数", [20, 50, 100], index=0)

try:
    data = api.list_runs(file_id=file_filter or None, status=status_filter or None, limit=limit)
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

runs = data.get("items", [])
if not runs:
    st.info("没有符合条件的记录。")
    st.stop()

st.markdown(f"##### 共 {data.get('total', len(runs))} 条记录")
ui.table(ui.summary_frame(runs))

run_map = {
    r["id"]: f"{r.get('file_name') or '未知文件'}｜{(r.get('created_at') or '')[:19].replace('T', ' ')}｜{ui.STATUS_TEXT.get(r['status'], r['status'])}"
    for r in runs
}
picked = st.selectbox("选择一条查看详情", options=[""] + list(run_map.keys()),
                      format_func=lambda x: "请选择…" if x == "" else run_map[x])

if not picked:
    st.stop()

try:
    run = api.get_run(picked)
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

st.divider()
ui.render_run(run, key_prefix=f"hist-{picked[:6]}")

col1, col2 = st.columns([1, 3])
with col1:
    st.download_button(
        "⬇️ 导出报告",
        data=api.to_json_bytes(run),
        file_name=f"analysis-{picked}.json",
        mime="application/json",
        width="stretch",
    )
with col2:
    if st.button("🗑️ 删除这条记录"):
        try:
            api.delete_run(picked)
            st.success("已删除")
            st.rerun()
        except api.ApiError as exc:
            st.error(str(exc))
