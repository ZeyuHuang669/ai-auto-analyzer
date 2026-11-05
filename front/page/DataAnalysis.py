import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from lib import api, ui

st.title("📊 数据分析")
st.caption("自动识别数据 → 统计分析 → 推荐并生成图表 → 生成结论 → 保存历史。")

run = st.session_state.get("current_run")

if run:
    header_left, header_right = st.columns([3, 1])
    with header_left:
        st.markdown(f"### {run.get('file_name', '')}")
    with header_right:
        st.download_button(
            "⬇️ 导出报告",
            data=api.to_json_bytes(run),
            file_name=f"analysis-{run.get('id', '')}.json",
            mime="application/json",
            width="stretch",
        )

    ui.render_run(run, key_prefix="current")

    st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔄 重新分析", width="stretch"):
            with st.spinner("重新分析中…"):
                try:
                    new_run = api.run_analysis(run["file_id"], use_ai=True, force=True)
                except api.ApiError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["current_run"] = new_run
                    st.rerun()
    with col2:
        if st.button("✖️ 关闭当前结果", width="stretch"):
            st.session_state.pop("current_run", None)
            st.rerun()
    st.stop()

# ---------------------------------------------------------------- 选择文件并分析
try:
    files = api.list_files(limit=100).get("items", [])
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

if not files:
    ui.empty_state(
        "还没有可分析的数据",
        "先去「文件」页上传一个 CSV 或 Excel。",
        page="page/Files.py",
        label="去上传文件",
    )
    st.stop()

with st.container(border=True):
    st.markdown("##### 选择数据并开始")
    id_to_file = {f["id"]: f for f in files}
    file_id = st.selectbox(
        "数据文件",
        options=list(id_to_file.keys()),
        format_func=lambda i: (
            f"{id_to_file[i]['name']}｜{id_to_file[i]['rows']:,} 行 × "
            f"{id_to_file[i]['cols']} 列"
        ),
    )
    col1, col2 = st.columns(2)
    with col1:
        use_ai = st.checkbox("用 AI 生成分析结论", value=True)
        st.caption("未配置模型时会自动使用规则结论，不影响其它功能。")
    with col2:
        force = st.checkbox("忽略缓存，强制重新计算", value=False)

    if st.button("🚀 开始自动分析", type="primary", width="stretch"):
        with st.spinner("正在自动识别 → 统计分析 → 推荐图表 → 生成结论…"):
            try:
                result = api.run_analysis(file_id, use_ai=use_ai, force=force)
            except api.ApiError as exc:
                st.error(str(exc))
            else:
                st.session_state["current_run"] = result
                st.rerun()

# ---------------------------------------------------------------- 最近分析
st.markdown("##### 最近的分析记录")
try:
    runs = api.list_runs(limit=8).get("items", [])
except api.ApiError:
    runs = []

if runs:
    ui.table(ui.summary_frame(runs))
    run_map = {
        r["id"]: f"{r.get('file_name') or r['file_id'][:6]}｜{(r.get('created_at') or '')[:19].replace('T', ' ')}"
        for r in runs
    }
    pick = st.selectbox("查看某条历史结果", options=[""] + list(run_map.keys()),
                        format_func=lambda x: "请选择…" if x == "" else run_map[x])
    if pick:
        try:
            st.session_state["current_run"] = api.get_run(pick)
            st.rerun()
        except api.ApiError as exc:
            st.error(str(exc))
else:
    st.caption("还没有分析记录。")
