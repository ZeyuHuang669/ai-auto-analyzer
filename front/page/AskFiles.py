import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from lib import api, ui

st.title("💬 问数据")
st.caption("知识问答基于 RAG 检索字段/发现/图表；智能分析会让 Planner 现算一次并出图。")

try:
    files = api.list_files(limit=200).get("items", [])
except api.ApiError as exc:
    st.error(str(exc))
    st.stop()

if not files:
    ui.empty_state("还没有数据可问", "先上传并分析一个文件。", "page/Files.py", "去上传")
    st.stop()

mode = st.radio(
    "模式",
    ["💬 知识问答（基于索引检索）", "🧭 智能分析（现场计算并出图）"],
    horizontal=True,
    label_visibility="collapsed",
)

is_planner = mode.startswith("🧭")
col1, col2 = st.columns([3, 1])
with col1:
    id_to_name = {f["id"]: f["name"] for f in files}
    scope = st.selectbox(
        "数据文件" if is_planner else "数据范围",
        options=(list(id_to_name.keys()) if is_planner else [""] + list(id_to_name.keys())),
        format_func=lambda x: (
            id_to_name[x] if x else "全部已索引文件"
        ),
        help="智能分析需要针对具体的一份数据集" if is_planner else None,
    )
with col2:
    st.write("")
    if st.button("重建索引", width="stretch", disabled=not scope):
        with st.spinner("重建索引中…"):
            try:
                res = api.reindex(scope)
                st.success(f"已索引 {res['chunks']} 个片段")
            except api.ApiError as exc:
                st.error(str(exc))

chat_key = "chat_rag" if mode.startswith("💬") else "chat_plan"
if chat_key not in st.session_state:
    st.session_state[chat_key] = []


def render_message(message: dict, index: int) -> None:
    with st.chat_message(message["role"], avatar="🧑" if message["role"] == "user" else "🤖"):
        if message["role"] == "user":
            st.write(message["content"])
            return

        if message.get("error"):
            st.error(message["error"])
            return

        st.write(message.get("answer", ""))
        if message.get("file_name"):
            st.caption(f"数据：{message['file_name']}")
        if message.get("engine"):
            st.caption(
                "模型生成" if message["engine"] == "llm" else "本地兜底（未配置模型或调用失败）"
            )

        charts = message.get("charts") or []
        for i, chart in enumerate(charts[:2]):
            st.markdown(f"**{chart['title']}**")
            st.caption(chart["reason"])
            ui.plotly(chart["figure"], height=340, key=f"chat-{index}-{i}")
            st.caption(f"💡 {chart['insight']}")

        if message.get("facts"):
            with st.expander("计算依据"):
                for fact in message["facts"]:
                    st.markdown(f"- {fact}")

        if message.get("steps"):
            with st.expander("执行计划"):
                st.json(message["steps"])

        sources = message.get("sources") or []
        if sources:
            with st.expander(f"引用来源（{len(sources)}）"):
                for s in sources:
                    st.markdown(
                        f"- **{s['title']}**（{s['kind']}，相似度 {s['score']:.2f}）"
                    )


if not st.session_state[chat_key]:
    with st.container(border=True):
        st.markdown("**试试这些问题**")
        samples = (
            ["哪个地区的销售额最高？", "数据里有哪些字段缺失？", "这张图和哪些字段有关？"]
            if chat_key == "chat_rag"
            else ["销售额最近几个月的趋势如何", "各个地区的销售额排名", "帮我整体介绍一下这份数据"]
        )
        for s in samples:
            st.markdown(f"- {s}")

for i, message in enumerate(st.session_state[chat_key]):
    render_message(message, i)

prompt = st.chat_input("输入你的问题…")
if prompt:
    st.session_state[chat_key].append({"role": "user", "content": prompt})
    with st.spinner("思考中…"):
        try:
            if chat_key == "chat_rag":
                result = api.ask(prompt, file_id=scope or None)
                st.session_state[chat_key].append(
                    {
                        "role": "assistant",
                        "answer": result["answer"],
                        "sources": result.get("sources", []),
                        "engine": result.get("engine"),
                    }
                )
            else:
                result = api.planner_run(prompt, file_id=scope or None)
                if result.get("error"):
                    st.session_state[chat_key].append(
                        {"role": "assistant", "answer": "", "error": result["error"]}
                    )
                else:
                    st.session_state[chat_key].append(
                        {
                            "role": "assistant",
                            "answer": result["answer"],
                            "charts": result.get("charts", []),
                            "facts": result.get("facts", []),
                            "steps": result.get("steps", []),
                            "engine": result.get("engine"),
                            "file_name": result.get("file_name"),
                        }
                    )
        except api.ApiError as exc:
            st.session_state[chat_key].append(
                {"role": "assistant", "answer": "", "error": str(exc)}
            )
    st.rerun()

if st.session_state[chat_key]:
    if st.button("清空对话"):
        st.session_state[chat_key] = []
        st.rerun()
