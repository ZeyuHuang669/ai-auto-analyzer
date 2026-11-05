# AI 自动化文件处理系统

上传 CSV / Excel → 自动识别数据 → 自动分析 → 自动推荐图表 → 自动出图 → AI 生成结论 → 保存分析历史。

Streamlit 前端 + FastAPI 后端，PostgreSQL/pgvector 与 SQLite 双支持，AI 不可用时自动降级为规则结论。

![主页](docs/screenshots/dashboard.png)

![自动分析结果](docs/screenshots/analysis.png)

---

## 一、对应你的需求

| 需求环节 | 实现位置 | 说明 |
| --- | --- | --- |
| 上传 CSV / Excel | `front/page/Files.py` → `POST /api/files/upload` | 支持多文件、CSV/TSV/Excel/JSON，按 sha256 去重 |
| 自动识别数据 | `backend/app/services/loader.py`、`profiler.py` | 自动识别编码（UTF-8/GBK/GB18030…）、分隔符、表头行、工作表；推断日期/数值/布尔/文本；识别时间、指标、维度、标识、文本等语义角色 |
| 自动数据分析 | `backend/app/services/analysis.py` | 描述统计、相关性、时间趋势、分组对比、异常值、缺失/重复，并给出带分数的关键发现 |
| 自动推荐图表 | `backend/app/services/charts.py` | 规则引擎按字段角色打分（趋势线、柱状、饼图、散点、直方、箱线、热力、缺失率），并保证类型多样性 |
| 自动画图 | 同上（Plotly 图在服务端直接生成） | 后端返回 `figure` JSON，前端零计算直接渲染 |
| AI 生成结论 | `backend/app/services/insights.py` | 调大模型输出 JSON（结论/发现/建议/注意事项）；无 Key 或调用失败时用规则结论兜底 |
| 保存分析历史 | `AnalysisRun` 表 + `front/page/History.py` | 每次分析完整落库：画像、发现、图表、结论、耗时、模型 |
| RAG | `backend/app/services/rag.py` | 把数据集/字段/发现/图表切成片段，向量检索 + 关键词混合重排，支持问答与引用 |
| AI Planner | `backend/app/services/planner.py` | 自然语言 → 意图/字段 → 现场计算 → 回答 + 配图 |
| 自动化执行 | `backend/app/services/automation.py` | 监视目录，新文件自动跑完整流水线（后台协程定时扫描） |

---

## 二、目录结构

```
PythonProject1/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # FastAPI 入口 + 启动自动化扫描
│  │  ├─ core/                   # 配置、数据库、pgvector 初始化
│  │  ├─ models.py               # files / analysis_runs / rag_chunks / rag_chats / automation_rules
│  │  ├─ schemas.py              # 请求体模型
│  │  ├─ serializers.py          # ORM → dict
│  │  ├─ services/               # loader / profiler / analysis / charts / insights / rag / planner / pipeline / automation / llm / embeddings / storage
│  │  └─ api/routes/             # files / analysis / rag / planner / automation / system
│  ├─ scripts/make_samples.py    # 生成示例数据
│  ├─ tests/                     # 32 个 pytest 用例
│  └─ requirements.txt
├─ front/
│  ├─ app.py                     # st.navigation 多页入口
│  ├─ lib/api.py                 # 后端客户端
│  ├─ lib/ui.py                  # 结果渲染组件（指标/图表/发现/结论）
│  └─ page/                      # 主页、文件、自动化、数据分析、历史、询问
├─ data/                         # SQLite、上传副本、示例数据
├─ .env / .env.example
└─ run_dev.ps1                   # 一键启动前后端
```

---

## 三、快速开始

### 1. 安装依赖

```powershell
cd C:\Users\Administrator\PycharmProjects\PythonProject1
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 2. 启动后端（终端 1）

```powershell
cd backend
$env:PYTHONPATH="C:\Users\Administrator\PycharmProjects\PythonProject1\backend"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>

### 3. 启动前端（终端 2）

```powershell
cd front
..\.venv\Scripts\python.exe -m streamlit run app.py
```

打开 <http://localhost:8501>。也可以直接双击 `run_dev.ps1` 一键起两个窗口。

**PyCharm 用户**：项目已带两个运行配置（右上角下拉框可见）
「后端 FastAPI (8000)」和「前端 Streamlit (8501)」，分别对应 `backend/run_server.py` 与 `front/run_app.py`，点两下 Run 即可，不需要配 PYTHONPATH。

### 4. 生成示例数据（可选）

```powershell
cd backend
..\.venv\Scripts\python.exe scripts\make_samples.py
```

会生成 `data/samples/sales_2024.csv`（906 行）和 `employees.xlsx`（260 行，2 个工作表），可直接拖进「文件」页。

---

## 四、配置

复制 `.env.example` 为 `.env`（仓库里已带一份默认的 `.env`），关键项：

```ini
# AI 模型（OpenAI 兼容协议）
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=            # 用中转服务时填，例如 https://api.xxx.com/v1
LLM_MODEL=gpt-4o-mini
USE_AI_INSIGHTS=true

# 向量：留空用本地哈希向量（离线可用）
EMBEDDING_MODEL=            # 填 text-embedding-3-small 则调用 API
EMBEDDING_DIM=512

# 数据库：不填默认 SQLite
# DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/ai_auto
```

> 没有 Key 也能完整使用：结论会走规则版（界面上标「规则兜底」），其它功能不受影响。

### 切换到 PostgreSQL + pgvector

```powershell
# 1. 在库上执行 scripts/init_pg.sql（创建数据库与 vector 扩展）
# 2. 安装驱动
.\.venv\Scripts\python.exe -m pip install "psycopg[binary]" pgvector
# 3. 修改 .env
DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/ai_auto
```

后端启动时会自动 `CREATE EXTENSION`、加 `embedding_vec` 列并建 HNSW 索引；扩展不可用时自动退回「JSON 向量 + numpy 余弦」，功能不中断（`/api/health` 里的 `vector_mode` 会显示当前模式）。

---

## 五、API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` `/api/stats` `/api/config` | 健康检查、看板统计、非敏感配置 |
| POST | `/api/files/upload` | 多文件上传（multipart） |
| GET | `/api/files` `/api/files/{id}` `/api/files/{id}/preview` | 列表、详情、前 N 行预览 |
| DELETE | `/api/files/{id}` | 删除文件及其分析记录 |
| POST | `/api/analysis/{file_id}/run?use_ai=true&force=false` | 跑完整流水线 |
| GET | `/api/analysis/runs` `/api/analysis/runs/{id}` | 历史列表 / 详情 |
| GET | `/api/analysis/runs/{id}/export` | 导出 JSON 报告 |
| POST | `/api/rag/ask` `/api/rag/index/{file_id}` | 知识问答 / 重建索引 |
| POST | `/api/planner/run` | 自然语言分析 |
| GET/POST/PATCH/DELETE | `/api/automation/rules…` | 自动化规则 CRUD |
| POST | `/api/automation/scan` `/api/automation/rules/{id}/scan` | 立即扫描 |

---

## 六、测试

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

覆盖：编码/分隔符识别、前导零编号、多工作表、字段角色、质量评分、相关性/趋势/分组、图表推荐与序列化、规则结论、上传去重、分析、RAG、Planner、自动化扫描。

前端页面用 Streamlit `AppTest` 验证（0 异常），关键交互（点分析、预览、提问）均已跑通。

---

## 七、已知限制与后续建议

1. **当前 `.env` 的 OpenAI Key 已过期**（调用返回 401），所以界面标记「规则兜底」。换新 Key 后无需改代码，AI 结论会自动启用。
2. 本地哈希向量只做字面相似度，问答召回一般；配好 `EMBEDDING_MODEL` 后质量会明显提升。
3. 分析是同步接口，超大文件（>50 万行）建议改成后台任务 + 轮询；当前上传上限 50 MB。
4. 自动化扫描是轮询实现（默认 60 秒），如需秒级触发可换成 watchdog。
5. 多用户/权限尚未实现，现在是单机单用户形态。
