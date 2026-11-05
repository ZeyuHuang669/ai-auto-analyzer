import streamlit as st

from lib.api import base_url

st.set_page_config(
    page_title="AI自动化文件处理系统",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

dashboard_page = st.Page(
    "page/DashBoard.py",
    title="主页",
    icon="🏠",
    default=True,
)

files_page = st.Page(
    "page/Files.py",
    title="文件",
    icon="📁",
)

automation_page = st.Page(
    "page/AutoMation.py",
    title="自动化文件设置",
    icon="⚙️",
)

dataanalysis_page = st.Page(
    "page/DataAnalysis.py",
    title="数据分析",
    icon="📊",
)

history_page = st.Page(
    "page/History.py",
    title="浏览历史",
    icon="⬆️",
)

askfiles_page = st.Page(
    "page/AskFiles.py",
    title="询问",
    icon="💬",
)

navigation = st.navigation(
    [
        dashboard_page,
        files_page,
        automation_page,
        dataanalysis_page,
        history_page,
        askfiles_page,
    ]
)

with st.sidebar:
    st.caption(f"后端：{base_url()}")

navigation.run()
