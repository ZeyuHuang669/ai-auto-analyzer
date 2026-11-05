import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from lib import api, ui

st.title("⚙️ 自动化")
st.caption("监视一个目录，出现新的 CSV / Excel 就自动跑完整分析并入库，无需手动操作。")

try:
    data = api.list_rules()
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

rules = data.get("items", [])
default_dir = data.get("default_dir", "")

# ---------------------------------------------------------------- 新建规则
with st.expander("➕ 新建自动化规则", expanded=not rules):
    with st.form("new_rule"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("规则名称", value="销售日报自动分析")
            watch_dir = st.text_input("监视目录", value=default_dir)
            pattern = st.text_input("文件匹配", value="*.csv", help="例如 *.csv 或 *.xlsx")
        with col2:
            use_ai = st.checkbox("自动调用 AI 生成结论", value=True)
            interval = st.number_input("扫描间隔（秒）", min_value=10, max_value=3600, value=60, step=10)
            st.caption("后端启动时会按这个间隔轮询目录。")
        submitted = st.form_submit_button("创建规则", type="primary")
        if submitted:
            try:
                api.create_rule(
                    {
                        "name": name,
                        "watch_dir": watch_dir,
                        "pattern": pattern or "*",
                        "enabled": True,
                        "use_ai": use_ai,
                        "interval_seconds": int(interval),
                    }
                )
                st.success("规则已创建")
                st.rerun()
            except api.ApiError as exc:
                st.error(str(exc))

if not rules:
    st.info("还没有自动化规则。创建一个试试，或者把文件放进示例目录后点「立即扫描」。")
else:
    st.markdown("##### 规则列表")
    for rule in rules:
        with st.container(border=True):
            info, actions = st.columns([3, 2])
            with info:
                st.markdown(
                    ui.chip(rule["name"], "#4C78A8")
                    + ui.chip(
                        "已启用" if rule["enabled"] else "已停用",
                        "#54A24B" if rule["enabled"] else "#999",
                    )
                    + ui.chip(rule["pattern"], "#888"),
                    unsafe_allow_html=True,
                )
                st.caption(f"监视目录：`{rule['watch_dir']}`")
                st.caption(
                    f"已处理 {rule['processed_count']} 个文件｜"
                    f"上次扫描 {ui.fmt_time(rule['last_scanned_at'], '%Y-%m-%d %H:%M')}"
                )
                if rule.get("last_error"):
                    st.warning(rule["last_error"], icon="⚠️")

            with actions:
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    enabled = st.toggle(
                        "启用", value=rule["enabled"], key=f"toggle-{rule['id']}"
                    )
                with col_b:
                    if st.button("立即扫描", key=f"scan-{rule['id']}", width="stretch"):
                        with st.spinner("扫描中…"):
                            try:
                                res = api.scan_rule(rule["id"])
                                st.success(
                                    f"发现 {res['found']}｜处理 {res['processed']}｜"
                                    f"跳过 {res['skipped']}"
                                )
                                if res.get("errors"):
                                    for err in res["errors"]:
                                        st.warning(err)
                            except api.ApiError as exc:
                                st.error(str(exc))
                with col_c:
                    if st.button("删除", key=f"del-{rule['id']}", width="stretch"):
                        try:
                            api.delete_rule(rule["id"])
                            st.rerun()
                        except api.ApiError as exc:
                            st.error(str(exc))

                if enabled != rule["enabled"]:
                    try:
                        api.update_rule(rule["id"], {"enabled": enabled})
                        st.rerun()
                    except api.ApiError as exc:
                        st.error(str(exc))

st.divider()
col1, col2 = st.columns([1, 2])
with col1:
    if st.button("▶️ 立即扫描全部规则", type="primary", width="stretch"):
        with st.spinner("正在扫描…"):
            try:
                res = api.scan_all()
                st.success(
                    f"{res['rules']} 条规则｜发现 {res['found']} 个文件｜"
                    f"处理 {res['processed']} 个"
                )
            except api.ApiError as exc:
                st.error(str(exc))
with col2:
    st.caption(
        "提示：把文件放进监视目录后，最迟一个扫描间隔就会自动分析。"
        "自动化产生的记录会标记为「自动」。"
    )

# ---------------------------------------------------------------- 自动化运行记录
st.markdown("##### 自动化运行记录")
try:
    runs = api.automation_runs(limit=20).get("items", [])
except api.ApiError:
    runs = []

if runs:
    ui.table(ui.summary_frame(runs))
    with st.expander("查看结论摘要"):
        for r in runs[:10]:
            st.markdown(f"- **{r.get('file_name') or '未知'}**：{r.get('summary') or '—'}")
else:
    st.caption("还没有自动化运行记录。")
