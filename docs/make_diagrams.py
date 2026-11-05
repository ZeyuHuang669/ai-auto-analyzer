"""生成技术文档用的架构图与流程图（纯 PIL，无额外依赖）。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)

FONT_DIR = Path(r"C:\Windows\Fonts")
REG = FONT_DIR / "msyh.ttc"
BOLD = FONT_DIR / "msyhbd.ttc"

INK = "#1F2937"
MUTED = "#5B6673"
BLUE = "#2F5D8C"
BLUE_FILL = "#E9F0F9"
GREEN = "#3C7A46"
GREEN_FILL = "#EAF4EC"
ORANGE = "#A65A12"
ORANGE_FILL = "#FDF2E7"
PANEL = "#F8FAFC"
PANEL_LINE = "#D7DFEA"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(BOLD if bold else REG), size, index=0)


def text_size(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont):
    box = draw.textbbox((0, 0), text, font=f)
    return box[2] - box[0], box[3] - box[1]


def center_text(draw, box, text, f, color=INK):
    x0, y0, x1, y1 = box
    w, h = text_size(draw, text, f)
    draw.text(((x0 + x1 - w) / 2, (y0 + y1 - h) / 2 - 2), text, font=f, fill=color)


def card(draw, box, text, f, fill=BLUE_FILL, line=BLUE, color=INK, radius=12, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=line, width=width)
    center_text(draw, box, text, f, color)


def panel(draw, box, title, f_title, fill=PANEL, line=PANEL_LINE):
    draw.rounded_rectangle(box, radius=16, fill=fill, outline=line, width=2)
    x0, y0, _, _ = box
    draw.text((x0 + 24, y0 + 16), title, font=f_title, fill=BLUE)


def arrow(draw, start, end, color="#8A96A6", width=3, head=13, dashed=False):
    x1, y1 = start
    x2, y2 = end
    if dashed:
        # 简单虚线
        total = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        steps = max(1, int(total // 14))
        for i in range(steps):
            if i % 2:
                continue
            t0, t1 = i / steps, min(1, (i + 0.7) / steps)
            draw.line(
                [(x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0),
                 (x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1)],
                fill=color, width=width,
            )
    else:
        draw.line([start, end], fill=color, width=width)

    if x2 == x1:
        direction = 1 if y2 > y1 else -1
        draw.polygon(
            [(x2, y2), (x2 - head * 0.6, y2 - direction * head), (x2 + head * 0.6, y2 - direction * head)],
            fill=color,
        )
    else:
        direction = 1 if x2 > x1 else -1
        draw.polygon(
            [(x2, y2), (x2 - direction * head, y2 - head * 0.6), (x2 - direction * head, y2 + head * 0.6)],
            fill=color,
        )


def label(draw, xy, text, f, color=MUTED):
    draw.text(xy, text, font=f, fill=color)


# --------------------------------------------------------------------------- #
# 图一：总体架构
# --------------------------------------------------------------------------- #
def architecture() -> Path:
    W, H = 1600, 1010
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    f_layer = font(28, bold=True)
    f_chip = font(21)
    f_note = font(18)
    f_small = font(17)

    # 用户
    card(d, (640, 26, 960, 88), "用  户", font(26, True), fill="#FFFFFF", line="#B9C4D2", radius=30)

    # 前端
    panel(d, (110, 132, 1490, 300), "Streamlit 前端  ·  :8501", f_layer)
    chips = ["主页看板", "文件管理", "数据分析", "历史记录", "智能问答", "自动化"]
    x = 150
    for name in chips:
        card(d, (x, 206, x + 200, 262), name, f_chip, fill="#FFFFFF", line="#9DB6D2", radius=10, width=2)
        x += 217

    # 后端
    panel(d, (110, 360, 1490, 508), "FastAPI 后端  ·  :8000", f_layer)
    chips = ["REST 路由", "参数校验", "依赖注入", "OpenAPI 文档"]
    x = 150
    for name in chips:
        card(d, (x, 434, x + 250, 486), name, f_chip, fill="#FFFFFF", line="#9DB6D2", radius=10, width=2)
        x += 266

    # 业务层
    panel(d, (110, 568, 1490, 736), "业务逻辑层", f_layer)
    biz = [
        ("文件管理", "保存 · 解析 · 去重"),
        ("数据分析", "统计 · 发现 · 评分"),
        ("自动化执行", "目录监听 · 定时扫描"),
        ("AI Planner", "意图识别 · 现场计算"),
        ("RAG", "索引 · 检索 · 问答"),
    ]
    x = 150
    for name, sub in biz:
        box = (x, 626, x + 240, 714)
        d.rounded_rectangle(box, radius=12, fill=BLUE_FILL, outline=BLUE, width=2)
        nw, nh = text_size(d, name, font(23, True))
        d.text((x + (240 - nw) / 2, 638), name, font=font(23, True), fill=INK)
        sw, _ = text_size(d, sub, f_small)
        d.text((x + (240 - sw) / 2, 676), sub, font=f_small, fill=MUTED)
        x += 258

    # 数据层
    d.rounded_rectangle((110, 790, 790, 966), radius=16, fill=ORANGE_FILL, outline="#E2C3A4", width=2)
    d.text((134, 806), "数据层", font=f_layer, fill=ORANGE)
    d.text((134, 846), "SQLite（默认） / PostgreSQL", font=font(20), fill=INK)
    d.text((134, 880), "五张业务表 + 向量索引（pgvector）", font=font(19), fill=MUTED)
    d.text((134, 918), "files · analysis_runs · rag_chunks", font=font(17), fill=MUTED)

    # AI
    d.rounded_rectangle((830, 790, 1490, 966), radius=16, fill=GREEN_FILL, outline="#B9D3BE", width=2)
    d.text((854, 806), "AI 模型（OpenAI 兼容协议）", font=f_layer, fill=GREEN)
    d.text((854, 846), "结论生成 · 知识问答 · 意图规划", font=font(20), fill=INK)
    d.text((854, 880), "Embedding 可选（默认本地哈希向量）", font=font(19), fill=MUTED)
    d.text((854, 918), "调用失败 → 自动降级为规则结论", font=font(17), fill=MUTED)

    # 箭头
    arrow(d, (800, 88), (800, 128))
    label(d, (812, 92), "HTTP", f_note)

    arrow(d, (800, 300), (800, 356))
    label(d, (812, 310), "HTTP / JSON（REST）", f_note)

    arrow(d, (800, 508), (800, 564))
    label(d, (812, 518), "服务调用", f_note)

    arrow(d, (450, 736), (450, 786))
    label(d, (462, 742), "SQLAlchemy ORM", f_note)

    arrow(d, (1160, 736), (1160, 786))
    label(d, (1172, 742), "HTTPS", f_note)

    arrow(d, (830, 878), (794, 878), color="#54A24B", width=3)
    label(d, (742, 844), "向量", f_note, color="#3C7A46")

    img.save(OUT / "architecture.png")
    return OUT / "architecture.png"


# --------------------------------------------------------------------------- #
# 图二：自动分析流程
# --------------------------------------------------------------------------- #
def flow() -> Path:
    W, H = 1600, 310
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    steps = [
        ("上传文件", "CSV / Excel\nJSON"),
        ("自动识别", "编码 · 分隔符\n字段语义"),
        ("统计分析", "描述 · 相关\n趋势 · 分组"),
        ("推荐图表", "规则打分\n排序去重"),
        ("生成图表", "Plotly\nfigure JSON"),
        ("AI 结论", "模型生成\n或规则兜底"),
        ("保存历史", "入库 + 建索引\n供问答复用"),
    ]

    box_w, gap = 190, 34
    total = len(steps) * box_w + (len(steps) - 1) * gap
    x = (W - total) // 2
    y0, y1 = 46, 246

    f_step = font(16, True)
    f_name = font(27, True)
    f_sub = font(18)

    for i, (name, sub) in enumerate(steps):
        box = (x, y0, x + box_w, y1)
        d.rounded_rectangle(box, radius=14, fill=BLUE_FILL, outline=BLUE, width=2)
        d.text((x + 16, y0 + 14), f"STEP {i + 1}", font=f_step, fill="#6B89AC")
        nw, _ = text_size(d, name, f_name)
        d.text((x + (box_w - nw) / 2, y0 + 56), name, font=f_name, fill=INK)
        for j, line in enumerate(sub.split("\n")):
            sw, _ = text_size(d, line, f_sub)
            d.text((x + (box_w - sw) / 2, y0 + 108 + j * 26), line, font=f_sub, fill=MUTED)
        if i < len(steps) - 1:
            arrow(d, (x + box_w + 6, (y0 + y1) // 2), (x + box_w + gap - 8, (y0 + y1) // 2), width=3)
        x += box_w + gap

    img.save(OUT / "flow.png")
    return OUT / "flow.png"


if __name__ == "__main__":
    print(architecture())
    print(flow())
