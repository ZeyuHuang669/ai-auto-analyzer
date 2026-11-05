import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from lib import api, ui

st.title("🏠 AI 自动化文件处理系统")
st.caption("上传 CSV / Excel → 自动识别 → 自动分析 → 自动选图出图 → AI 结论 → 保存历史")

# ---------------------------------------------------------------- 健康检查
try:
    health = api.health()
    stats = api.stats()
except api.ApiError as exc:
    st.error("后端未启动")
    st.markdown(str(exc))
    st.markdown("**启动命令（在 PyCharm 的 Terminal 里执行）：**")
    st.code(
        "cd backend\n"
        "uvicorn app.main:app --reload --port 8000",
        language="powershell",
    )
    st.markdown("**再开一个终端启动前端：**")
    st.code(
        "cd front\nstreamlit run app.py",
        language="powershell",
    )
    st.stop()

ai_on = health.get("ai_available")
st.markdown(
    ui.chip("后端在线", "#54A24B")
    + ui.chip(f"AI：{'可用' if ai_on else '未配置（用规则结论）'}", "#4C78A8" if ai_on else "#999")
    + ui.chip(f"向量检索：{health.get('vector_mode')}", "#72B7B2")
    + ui.chip(f"存储：{stats['storage']['mb']} MB", "#888"),
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- 指标
files = stats.get("files", {})
runs = stats.get("runs", {})
col1, col2, col3, col4 = st.columns(4)
col1.metric("文件数", files.get("total", 0))
col2.metric("累计数据行", f"{files.get('rows', 0):,}")
col3.metric("分析次数", runs.get("total", 0))
col4.metric("知识片段", stats.get("rag", {}).get("chunks", 0))

if files.get("total", 0) == 0:
    st.divider()
    st.markdown("### 三步开始")
    a, b, c = st.columns(3)
    with a:
        with st.container(border=True):
            st.markdown("**① 上传数据**")
            st.write("CSV / Excel / JSON 都可以，自动识别编码和字段类型。")
            st.page_link("page/Files.py", label="去上传 →", icon="📁")
    with b:
        with st.container(border=True):
            st.markdown("**② 一键分析**")
            st.write("自动统计、找规律、推荐图表并生成结论。")
            st.page_link("page/DataAnalysis.py", label="去分析 →", icon="📊")
    with c:
        with st.container(border=True):
            st.markdown("**③ 直接提问**")
            st.write("用自然语言问数据，也能让 AI 规划一次分析。")
            st.page_link("page/AskFiles.py", label="去提问 →", icon="💬")
    st.stop()

# ---------------------------------------------------------------- 最近分析
st.divider()
st.markdown("### 最近分析")
recent = stats.get("recent_runs", [])
if recent:
    ui.table(ui.summary_frame(recent))

    latest = recent[0]
    if st.button("查看最近一次分析结果", type="primary"):
        try:
            st.session_state["current_run"] = api.get_run(latest["id"])
        except api.ApiError as exc:
            st.error(str(exc))
        else:
            st.switch_page("page/DataAnalysis.py")
else:
    st.caption("还没有分析记录。")

# ---------------------------------------------------------------- 系统信息
with st.expander("系统信息"):
    config = {}
    try:
        config = api.config()
    except api.ApiError:
        pass
    st.markdown(
        f"- 模型：`{config.get('model', '—')}`"
        f"（{'已配置' if config.get('ai_enabled') else '未配置 Key，结论走规则'}）\n"
        f"- 向量：`{config.get('vector_mode', '—')}` / `{config.get('embedding_model', '—')}`\n"
        f"- 数据库：`{config.get('database', '—')}`\n"
        f"- 数据目录：`{stats['storage'].get('path', '—')}`\n"
        f"- 支持格式：{', '.join(config.get('supported_formats', []))}"
    )
