"""生成《AI 自动化文件处理系统 技术设计文档》.docx

用法：
    python build_tech_doc.py
输出：
    docs/AI自动化文件处理系统-技术设计文档.docx
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
OUTPUT = HERE / "AI自动化文件处理系统-技术设计文档.docx"

INK = "1F2937"
NAVY = "1F3864"
BLUE = "2E5C8A"
MUTED = "5B6673"
BORDER = "BFC9D6"
HEADER_BG = "DCE6F2"
CODE_BG = "F4F5F7"

BODY_FONT = "宋体"
HEAD_FONT = "微软雅黑"
MONO_FONT = "Consolas"


# --------------------------------------------------------------------------- #
# 底层工具
# --------------------------------------------------------------------------- #
def set_run(run, *, font: str = BODY_FONT, size: float = 10.5, bold=None,
            color: str | None = None, italic=None):
    run.font.name = font
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)
    rfonts.set(qn("w:eastAsia"), font if font != MONO_FONT else HEAD_FONT)


def style_fonts(style, font: str, size: float, bold=None, color: str | None = None):
    style.font.name = font
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color:
        style.font.color.rgb = RGBColor.from_string(color)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)
    rfonts.set(qn("w:eastAsia"), HEAD_FONT if font != BODY_FONT else BODY_FONT)


def shade(cell, hex_color: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def para_shade(paragraph, hex_color: str):
    ppr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    ppr.append(shd)


def para_border(paragraph, edge: str = "bottom", color: str = BORDER, size: int = 6):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = ppr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        ppr.append(pbdr)
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), "4")
    el.set(qn("w:color"), color)
    pbdr.append(el)


def set_no_borders(table_obj):
    tbl_pr = table_obj._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tbl_pr.append(borders)


def add_field(paragraph, instr: str, *, size: float = 9, color: str = MUTED):
    run = paragraph.add_run()
    set_run(run, font=HEAD_FONT, size=size, color=color)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = f" {instr} "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr_el)
    run._r.append(separate)
    run._r.append(placeholder)
    run._r.append(end)


# --------------------------------------------------------------------------- #
# 文档构件
# --------------------------------------------------------------------------- #
def body(doc, text: str, *, size: float = 10.5, space_after: float = 6,
         indent: bool = True, color: str = INK, bold: bool = False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.45
    if indent:
        p.paragraph_format.first_line_indent = Pt(21)
    run = p.add_run(text)
    set_run(run, size=size, color=color, bold=bold)
    return p


def bullets(doc, items: list[str], *, size: float = 10.5):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.4
        run = p.add_run(item)
        set_run(run, size=size)


def numbered(doc, items: list[str], *, size: float = 10.5):
    """手动编号：Word 的 List Number 会跨列表连续编号，这里自己控制。"""
    for i, item in enumerate(items, 1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.95)
        pf.first_line_indent = Cm(-0.95)
        pf.space_after = Pt(3)
        pf.line_spacing = 1.4
        run = p.add_run(f"{i}.   ")
        set_run(run, size=size)
        run = p.add_run(item)
        set_run(run, size=size)


def code(doc, text: str, *, size: float = 8.6):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(4)
    pf.space_after = Pt(8)
    pf.line_spacing = 1.15
    pf.left_indent = Cm(0.45)
    pf.right_indent = Cm(0.2)
    para_shade(p, CODE_BG)
    lines = text.strip("\n").split("\n")
    for i, line in enumerate(lines):
        run = p.add_run(line)
        set_run(run, font=MONO_FONT, size=size, color="2B3440")
        if i < len(lines) - 1:
            run.add_break()
    return p


def caption(doc, text: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run(text)
    set_run(run, font=HEAD_FONT, size=9, color=MUTED)


def figure(doc, path: Path, width_cm: float, cap: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    caption(doc, cap)


def table(doc, headers: list[str], rows: list[list[str]], widths: list[float],
          cap: str | None = None, font_size: float = 8.8, header_size: float = 9):
    table_obj = doc.add_table(rows=1, cols=len(headers))
    table_obj.style = "Table Grid"
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_obj.autofit = False

    # 列宽（table grid + 每个单元格）
    for idx, width in enumerate(widths):
        table_obj.columns[idx].width = Cm(width)

    hdr = table_obj.rows[0]
    tr_pr = hdr._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)

    for idx, text in enumerate(headers):
        cell = hdr.cells[idx]
        cell.width = Cm(widths[idx])
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        shade(cell, HEADER_BG)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(2)
        run = p.add_run(text)
        set_run(run, font=HEAD_FONT, size=header_size, bold=True, color=NAVY)

    for row_data in rows:
        row = table_obj.add_row()
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        for idx, text in enumerate(row_data):
            cell = row.cells[idx]
            cell.width = Cm(widths[idx])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.line_spacing = 1.2
            run = p.add_run(str(text))
            set_run(run, size=font_size)

    if cap:
        caption(doc, cap)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return table_obj


def h1(doc, text: str):
    p = doc.add_paragraph(style="Heading 1")
    run = p.add_run(text)
    set_run(run, font=HEAD_FONT, size=17, bold=True, color=NAVY)
    return p


def h2(doc, text: str):
    p = doc.add_paragraph(style="Heading 2")
    run = p.add_run(text)
    set_run(run, font=HEAD_FONT, size=13, bold=True, color=BLUE)
    return p


def h3(doc, text: str):
    p = doc.add_paragraph(style="Heading 3")
    run = p.add_run(text)
    set_run(run, font=HEAD_FONT, size=11, bold=True, color="333F4F")
    return p


# --------------------------------------------------------------------------- #
# 版式
# --------------------------------------------------------------------------- #
def setup(doc: Document):
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Cm(2.4)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.6)
    section.header_distance = Cm(1.2)
    section.footer_distance = Cm(1.0)
    section.different_first_page_header_footer = True

    styles = doc.styles
    normal = styles["Normal"]
    style_fonts(normal, BODY_FONT, 10.5, color=INK)
    normal.paragraph_format.line_spacing = 1.45
    normal.paragraph_format.space_after = Pt(6)

    h1_style = styles["Heading 1"]
    style_fonts(h1_style, HEAD_FONT, 17, bold=True, color=NAVY)
    h1_style.paragraph_format.space_before = Pt(20)
    h1_style.paragraph_format.space_after = Pt(10)
    h1_style.paragraph_format.keep_with_next = True

    h2_style = styles["Heading 2"]
    style_fonts(h2_style, HEAD_FONT, 13, bold=True, color=BLUE)
    h2_style.paragraph_format.space_before = Pt(14)
    h2_style.paragraph_format.space_after = Pt(6)
    h2_style.paragraph_format.keep_with_next = True

    h3_style = styles["Heading 3"]
    style_fonts(h3_style, HEAD_FONT, 11, bold=True, color="333F4F")
    h3_style.paragraph_format.space_before = Pt(10)
    h3_style.paragraph_format.space_after = Pt(4)
    h3_style.paragraph_format.keep_with_next = True

    for name in ("List Bullet", "List Number"):
        st = styles[name]
        style_fonts(st, BODY_FONT, 10.5, color=INK)

    # 页眉
    # 默认 Header 样式自带居中/右制表位（按 Letter 尺寸），先改成 A4 的右对齐制表位
    header_style = styles["Header"]
    header_style.paragraph_format.tab_stops.clear_all()
    header_style.paragraph_format.tab_stops.add_tab_stop(
        Cm(15.4), WD_TAB_ALIGNMENT.RIGHT
    )

    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hp.paragraph_format.tab_stops.clear_all()
    run = hp.add_run("AI 自动化文件处理系统  ·  技术设计文档")
    set_run(run, font=HEAD_FONT, size=8.5, color=MUTED)
    run = hp.add_run("\tV1.0")
    set_run(run, font=HEAD_FONT, size=8.5, color=MUTED)
    para_border(hp, "bottom", BORDER, 4)

    # 页脚
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run("第 ")
    set_run(run, font=HEAD_FONT, size=8.5, color=MUTED)
    add_field(fp, "PAGE", size=8.5)
    run = fp.add_run(" 页 / 共 ")
    set_run(run, font=HEAD_FONT, size=8.5, color=MUTED)
    add_field(fp, "NUMPAGES", size=8.5)
    run = fp.add_run(" 页")
    set_run(run, font=HEAD_FONT, size=8.5, color=MUTED)

    props = doc.core_properties
    props.title = "AI 自动化文件处理系统 技术设计文档"
    props.subject = "上传-识别-分析-图表-AI结论 全链路技术方案"
    props.author = "项目组"
    props.keywords = "FastAPI;Streamlit;数据分析;RAG;pgvector;Plotly"
    props.comments = "V1.0 初稿"


def cover(doc: Document):
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("技 术 设 计 文 档")
    set_run(run, font=HEAD_FONT, size=13, color=MUTED)
    p.paragraph_format.space_after = Pt(24)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("AI 自动化文件处理系统")
    set_run(run, font=HEAD_FONT, size=30, bold=True, color=NAVY)
    p.paragraph_format.space_after = Pt(8)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("上传 · 识别 · 分析 · 可视化 · AI 结论  一体化平台")
    set_run(run, font=HEAD_FONT, size=12, color=BLUE)
    p.paragraph_format.space_after = Pt(10)

    rule = doc.add_paragraph()
    rule.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = rule.add_run("—" * 26)
    set_run(run, font=HEAD_FONT, size=10, color=BORDER)
    rule.paragraph_format.space_after = Pt(40)

    info = [
        ("文档版本", "V1.0（初稿）"),
        ("编写日期", "2026 年 11 月 4 日"),
        ("系统形态", "Streamlit + FastAPI 单机部署，支持 PostgreSQL / SQLite"),
        ("技术栈", "Python 3.13 · Streamlit 1.64 · FastAPI 0.162 · pandas 3.0 · Plotly 7.1"),
        ("代码位置", "PythonProject1 工程根目录（详见第 8 章）"),
    ]
    table_obj = doc.add_table(rows=0, cols=2)
    table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_obj.autofit = False
    set_no_borders(table_obj)
    for key, value in info:
        row = table_obj.add_row()
        c0, c1 = row.cells
        c0.width = Cm(3.4)
        c1.width = Cm(10.4)
        c0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p0.paragraph_format.space_after = Pt(6)
        run = p0.add_run(key)
        set_run(run, font=HEAD_FONT, size=9.5, color=MUTED)
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(6)
        p1.paragraph_format.left_indent = Cm(0.2)
        run = p1.add_run(value)
        set_run(run, size=9.5)

    for _ in range(2):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("内 部 资 料")
    set_run(run, font=HEAD_FONT, size=9, color=MUTED)

    doc.add_page_break()


def toc(doc: Document):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("目　　录")
    set_run(run, font=HEAD_FONT, size=18, bold=True, color=NAVY)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(18)

    entries = [
        (1, "1  文档说明"),
        (2, "1.1  编写目的"),
        (2, "1.2  读者对象"),
        (2, "1.3  术语与缩写"),
        (2, "1.4  修订记录"),
        (1, "2  系统概述"),
        (2, "2.1  建设背景"),
        (2, "2.2  设计目标"),
        (2, "2.3  核心业务流程"),
        (2, "2.4  功能清单"),
        (1, "3  总体架构"),
        (2, "3.1  分层架构"),
        (2, "3.2  各层职责"),
        (2, "3.3  技术选型"),
        (2, "3.4  部署拓扑"),
        (2, "3.5  关键设计决策"),
        (1, "4  接口设计"),
        (2, "4.1  设计约定"),
        (2, "4.2  接口清单"),
        (2, "4.3  典型接口示例"),
        (2, "4.4  错误处理与降级策略"),
        (1, "5  核心模块设计"),
        (2, "5.1  文件读取与类型推断"),
        (2, "5.2  数据识别与质量评分"),
        (2, "5.3  统计分析引擎"),
        (2, "5.4  图表推荐与生成"),
        (2, "5.5  AI 结论生成"),
        (2, "5.6  RAG 检索问答"),
        (2, "5.7  AI Planner"),
        (2, "5.8  自动化执行"),
        (2, "5.9  流水线编排与缓存"),
        (1, "6  数据模型"),
        (2, "6.1  实体关系"),
        (2, "6.2  表结构"),
        (2, "6.3  索引、级联与完整性"),
        (2, "6.4  PostgreSQL + pgvector 切换"),
        (1, "7  前端设计"),
        (2, "7.1  页面结构"),
        (2, "7.2  交互流程"),
        (2, "7.3  渲染组件"),
        (2, "7.4  异常与空状态"),
        (1, "8  部署与配置"),
        (2, "8.1  环境要求"),
        (2, "8.2  安装与启动"),
        (2, "8.3  配置项说明"),
        (2, "8.4  迁移到 PostgreSQL"),
        (2, "8.5  数据文件说明"),
        (1, "9  测试与验证"),
        (2, "9.1  测试策略"),
        (2, "9.2  用例分布"),
        (2, "9.3  端到端实测"),
        (2, "9.4  已知问题与限制"),
        (1, "10  后续演进建议"),
        (2, "10.1  短期（1–2 周）"),
        (2, "10.2  中期（1–2 个月）"),
        (2, "10.3  长期"),
        (1, "附录 A  项目目录结构"),
        (1, "附录 B  示例数据说明"),
        (1, "附录 C  常用命令速查"),
    ]

    for level, text in entries:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1.5)
        p.paragraph_format.space_before = Pt(4 if level == 1 else 0)
        p.paragraph_format.line_spacing = 1.1
        p.paragraph_format.left_indent = Cm(0.0 if level == 1 else 0.8)
        run = p.add_run(text)
        set_run(
            run,
            font=HEAD_FONT,
            size=10.5 if level == 1 else 9.5,
            bold=level == 1,
            color=NAVY if level == 1 else INK,
        )

    doc.add_page_break()


def chapter_1(doc: Document):
    h1(doc, "1  文档说明")

    h2(doc, "1.1  编写目的")
    body(
        doc,
        "本文档描述「AI 自动化文件处理系统」的设计目标、总体架构、核心模块、接口、数据模型、"
        "部署方式与测试验证情况，用于指导开发维护、二次开发与后续交接。文档内容与当前代码库一致，"
        "涉及的具体参数（阈值、权重、评分公式）均直接取自实现。",
    )
    body(
        doc,
        "系统的核心目标是把「拿到一份 CSV/Excel → 看懂数据 → 画图 → 写结论」这件重复劳动固化下来，"
        "让业务同学只做上传和提问两件事。",
    )

    h2(doc, "1.2  读者对象")
    bullets(
        doc,
        [
            "项目负责人：了解系统边界、能力与限制，评估后续投入。",
            "开发人员：按模块理解实现细节，进行功能扩展或缺陷修复。",
            "运维/部署人员：按第 8 章完成环境搭建与配置切换。",
            "测试人员：参考第 9 章的测试范围与用例分布设计回归用例。",
        ],
    )

    h2(doc, "1.3  术语与缩写")
    table(
        doc,
        ["术语", "英文/缩写", "含义"],
        [
            ["数据画像", "Profile", "对数据集的整体描述：行列规模、字段语义角色、缺失与重复情况、质量评分"],
            ["语义角色", "Role", "字段的业务含义分类：时间、数值指标、分类维度、布尔标记、标识、文本"],
            ["发现", "Finding", "由规则自动识别出的数据特征或问题，带类型、说明与参考分"],
            ["图表规格", "Chart Spec", "描述一张图的类型、字段、聚合方式、推荐理由与 Plotly 图形 JSON"],
            ["兜底结论", "Fallback", "未配置模型或调用失败时，由规则模板生成的结论"],
            ["片段", "Chunk", "RAG 索引的最小检索单元，如某字段说明、某条发现、某张图的解读"],
            ["规划器", "Planner", "把自然语言问题翻译成分析动作并执行的模块"],
            ["向量检索", "Vector Search", "按语义相似度召回片段，本项目支持 pgvector 与本地余弦两种实现"],
        ],
        widths=[2.6, 3.0, 9.8],
        cap="表 1-1  术语与缩写",
    )

    h2(doc, "1.4  修订记录")
    table(
        doc,
        ["版本", "日期", "修订说明", "作者"],
        [["V1.0", "2026-11-04", "首次成文，覆盖架构、模块、接口、数据模型、部署与测试", "项目组"]],
        widths=[2.2, 3.0, 8.2, 2.0],
        cap="表 1-2  修订记录",
    )


def chapter_2(doc: Document):
    h1(doc, "2  系统概述")

    h2(doc, "2.1  建设背景")
    body(
        doc,
        "日常经营分析中，业务同学拿到的往往是一份原始导出表：字段命名不统一、日期是文本、金额带千分位、"
        "还有缺失和重复。要得到一张能看的图和几句结论，通常要经历「清洗—试算—调图—写话」四步，"
        "同一个动作每周重复，且高度依赖个人经验。",
    )
    body(
        doc,
        "本系统把这条链路固化为服务：上传文件后自动完成识别、统计、选图、出图与结论生成，并把结果留档，"
        "支持回看历史与自然语言追问。",
    )

    h2(doc, "2.2  设计目标")
    numbered(
        doc,
        [
            "零配置可用：默认 SQLite + 本地向量，不装数据库、不配 API Key 也能完整跑通全流程。",
            "AI 可降级：模型只做增强，任何调用失败都必须有可用结果，不能成为单点故障。",
            "结果可解释：每张图都给出「为什么选它」，每条发现都带数据依据，避免黑箱输出。",
            "可平滑升级：SQLite 换 PostgreSQL/pgvector、本地向量换 API 向量、同步换异步，均不触动业务代码。",
        ],
    )

    h2(doc, "2.3  核心业务流程")
    figure(doc, ASSETS / "flow.png", 15.3, "图 2-1  自动分析主流程")
    bullets(
        doc,
        [
            "全流程默认在 1 秒内完成（906 行示例数据实测约 0.4 秒），不依赖外部服务即可产出图表与统计结论。",
            "AI 环节是增强项：未配置 Key 或调用失败时自动降级为规则结论，其余步骤不受影响。",
            "分析结果同时写入 RAG 索引，可直接用自然语言追问，无需重复上传。",
        ],
    )
    table(
        doc,
        ["步骤", "输入", "处理要点", "输出"],
        [
            ["1. 上传", "CSV / Excel / JSON", "格式与大小校验，按 SHA-256 去重，落盘并登记", "文件记录 + 原始副本"],
            ["2. 识别", "文件字节流", "编码探测、分隔符嗅探、表头定位、多工作表选择、类型推断", "DataFrame + 读取元信息"],
            ["3. 分析", "DataFrame", "描述统计、相关性、趋势、分组对比、异常与缺失检查", "统计结果 + 关键发现"],
            ["4. 选图", "画像 + 统计结果", "按语义角色生成候选图表并打分排序，控制类型多样性", "图表规格列表"],
            ["5. 出图", "图表规格", "服务端用 Plotly 生成图形 JSON", "可直接渲染的 figure"],
            ["6. 结论", "画像 + 统计 + 图表", "模型生成结构化结论；失败时用规则模板", "结论 / 发现 / 建议 / 注意事项"],
            ["7. 留档", "全部结果", "写入分析记录，同时切片建索引", "历史记录 + 可检索片段"],
        ],
        widths=[2.2, 3.2, 7.4, 4.4],
        cap="表 2-1  流程步骤说明",
    )

    h2(doc, "2.4  功能清单")
    table(
        doc,
        ["功能", "说明", "入口", "状态"],
        [
            ["文件上传与解析", "多文件、多格式、自动识别编码与表头、按内容去重", "文件页 / POST /api/files/upload", "已实现"],
            ["数据自动识别", "字段语义角色、缺失重复、质量评分与问题清单", "文件页、分析页", "已实现"],
            ["自动统计分析", "描述统计、相关性、趋势、分组、异常值", "分析页 / 分析接口", "已实现"],
            ["图表推荐", "规则打分选图，同类型最多两张", "分析页「智能图表」", "已实现"],
            ["图表生成", "服务端生成 Plotly 图形，前端零计算渲染", "同上", "已实现"],
            ["AI 结论", "模型生成结论/发现/建议/注意事项，失败降级", "分析页「AI 结论」", "已实现"],
            ["分析历史", "全量留档，可回看、导出 JSON、删除", "历史页", "已实现"],
            ["知识问答（RAG）", "基于索引片段回答并给出引用来源", "询问页", "已实现"],
            ["智能分析（Planner）", "自然语言现场计算并配图", "询问页", "已实现"],
            ["自动化执行", "监视目录，新文件自动跑全流程", "自动化页", "已实现"],
            ["看板统计", "文件数、数据行、分析次数、片段数、最近记录", "主页", "已实现"],
        ],
        widths=[3.4, 7.2, 4.6, 1.8],
        cap="表 2-2  功能清单",
    )


def chapter_3(doc: Document):
    h1(doc, "3  总体架构")

    h2(doc, "3.1  分层架构")
    body(
        doc,
        "系统采用前后端分离的四层结构：展示层（Streamlit）、接口层（FastAPI）、业务层（服务模块）、"
        "数据层（关系库 + 向量索引），AI 模型作为业务层的外部依赖横向接入。",
    )
    figure(doc, ASSETS / "architecture.png", 15.6, "图 3-1  系统总体架构")

    h2(doc, "3.2  各层职责")
    table(
        doc,
        ["层次", "组成", "职责", "不做什么"],
        [
            ["展示层", "Streamlit 六个页面", "收集输入、调用接口、渲染结果", "不做统计计算、不直接连数据库"],
            ["接口层", "FastAPI 路由 + Pydantic", "协议转换、参数校验、错误映射、OpenAPI 文档", "不包含业务规则"],
            ["业务层", "loader / profiler / analysis / charts / insights / rag / planner / automation / pipeline", "全部业务规则与算法", "不感知 HTTP 细节"],
            ["数据层", "SQLAlchemy 模型 + SQLite/PostgreSQL", "持久化、迁移、向量索引", "不包含分析逻辑"],
            ["外部依赖", "OpenAI 兼容模型、Embedding 服务", "生成结论、问答、意图识别、向量化", "不允许阻塞主流程"],
        ],
        widths=[2.2, 5.2, 5.4, 3.4],
        cap="表 3-1  分层职责",
    )

    h2(doc, "3.3  技术选型")
    table(
        doc,
        ["层次", "技术", "版本", "选型理由"],
        [
            ["运行时", "Python", "3.13.15", "与数据分析生态一致，团队上手成本低"],
            ["前端", "Streamlit", "1.64.0", "纯 Python 多页应用，内置表格/图表/上传组件"],
            ["后端", "FastAPI", "0.162.0", "自动 OpenAPI、Pydantic 校验、性能足够"],
            ["Web 服务器", "Uvicorn", "0.53.0", "ASGI 标准实现，支持热重载"],
            ["ORM", "SQLAlchemy", "2.1.8", "同一套模型兼容 SQLite 与 PostgreSQL"],
            ["数据分析", "pandas / NumPy", "3.0.6 / 2.5.3", "表格处理与数值计算的事实标准"],
            ["可视化", "Plotly", "7.1.0", "服务端可直接输出图形 JSON，前端原样渲染"],
            ["模型调用", "OpenAI SDK", "3.45.0", "兼容任意 OpenAI 协议网关，便于切换模型"],
            ["配置", "pydantic-settings", "2.16.2", ".env 类型化读取，避免散落的 os.environ"],
            ["向量库", "pgvector（可选）", "—", "与业务表同库，避免额外中间件"],
        ],
        widths=[2.2, 3.4, 2.6, 8.0],
        cap="表 3-2  技术选型",
    )

    h2(doc, "3.4  部署拓扑")
    body(
        doc,
        "当前为单机双进程部署：后端监听 8000，前端监听 8501，前端通过 HTTP 访问后端；"
        "数据库默认是本地 SQLite 文件，切换为 PostgreSQL 时仅需修改连接串。",
    )
    table(
        doc,
        ["组件", "默认地址/路径", "说明"],
        [
            ["前端", "http://localhost:8501", "Streamlit，浏览器访问入口"],
            ["后端", "http://127.0.0.1:8000", "FastAPI，接口文档位于 /docs"],
            ["数据库", "data/app.db", "SQLite 文件；或 PostgreSQL 连接串"],
            ["上传副本", "data/uploads/<随机目录>/", "与原始文件同名，按 SHA-256 去重"],
            ["示例数据", "data/samples/", "自动生成的演示数据"],
            ["报告导出", "浏览器下载", "分析结果 JSON，也可从接口获取"],
        ],
        widths=[2.4, 6.4, 6.6],
        cap="表 3-3  部署组件",
    )

    h2(doc, "3.5  关键设计决策")
    h3(doc, "3.5.1  分析与绘图放在后端")
    body(
        doc,
        "所有统计与图表都在后端完成，前端只负责展示。这样同一套逻辑可以被页面、自动化任务、"
        "外部 API 复用；历史记录里存的是已经算好的图形数据，回看时不依赖原始文件仍然存在。",
    )

    h3(doc, "3.5.2  图表以 Plotly JSON 交付")
    body(
        doc,
        "后端返回的是完整的图形 JSON（data + layout），前端用 plotly.io.from_json 直接构造图对象。"
        "好处是前后端不会因为聚合口径不一致而画出两张不同的图；代价是图形 JSON 体积略大，"
        "对几十个数据点的图表可以忽略。",
    )

    h3(doc, "3.5.3  AI 是增强项而非依赖")
    body(
        doc,
        "模型调用统一经过 LLMClient，任何异常都被吞掉并记录日志，由规则结论兜底。"
        "界面会明确标注「模型生成」还是「规则兜底」，避免用户误以为结论来自模型。",
    )

    h3(doc, "3.5.4  默认 SQLite，可选 PostgreSQL")
    body(
        doc,
        "SQLite 让新同学克隆代码后直接可跑；PostgreSQL + pgvector 面向数据量与并发要求更高的场景。"
        "两者共用同一套 ORM 模型，pgvector 通过原生 DDL 补齐列与索引，不引入第二套代码路径。",
    )

    h3(doc, "3.5.5  混合检索而非纯向量")
    body(
        doc,
        "未配置 Embedding 时使用的是本地哈希向量，语义能力有限。因此在向量相似度之外，"
        "叠加关键词重叠度和「问题中点名字段」的加权，显著改善了离线场景的召回质量。",
    )


def chapter_4(doc: Document):
    h1(doc, "4  接口设计")

    h2(doc, "4.1  设计约定")
    bullets(
        doc,
        [
            "风格：REST，基础路径 /api，请求与响应均为 UTF-8 JSON（上传接口为 multipart/form-data）。",
            "时间：统一返回 UTC 的 ISO 8601 字符串（带 +00:00），由前端转换为本地时区展示。",
            "错误：非 2xx 响应体为 {\"detail\": \"可读的中文错误说明\"}；参数错误返回 422。",
            "幂等：上传按 SHA-256 去重，重复上传返回既有记录并置 duplicated=true；分析在参数一致时复用已有结果。",
            "同步语义：分析接口同步返回结果，常规数据量在 1 秒内；接入大模型时耗时取决于模型响应。",
        ],
    )

    h2(doc, "4.2  接口清单")
    table(
        doc,
        ["模块", "方法", "路径", "说明"],
        [
            ["系统", "GET", "/api/health", "健康检查：数据库、AI、向量模式"],
            ["系统", "GET", "/api/stats", "看板统计：文件、分析、片段、自动化、存储"],
            ["系统", "GET", "/api/config", "非敏感配置：模型名、上传上限、支持格式"],
            ["文件", "POST", "/api/files/upload", "上传一个或多个文件，自动解析并预热缓存"],
            ["文件", "GET", "/api/files", "文件列表，含分析次数"],
            ["文件", "GET", "/api/files/{id}", "文件详情：字段画像、片段数、最近分析"],
            ["文件", "GET", "/api/files/{id}/preview", "前 N 行预览与列类型"],
            ["文件", "DELETE", "/api/files/{id}", "删除文件及其分析记录、索引、副本"],
            ["分析", "POST", "/api/analysis/{file_id}/run", "对指定文件执行完整流水线"],
            ["分析", "POST", "/api/analysis/run", "同上，参数放在请求体"],
            ["分析", "GET", "/api/analysis/runs", "历史列表，支持按文件/状态过滤"],
            ["分析", "GET", "/api/analysis/runs/{id}", "单条分析完整结果"],
            ["分析", "GET", "/api/analysis/runs/{id}/export", "导出 JSON 报告（附件下载）"],
            ["分析", "DELETE", "/api/analysis/runs/{id}", "删除一条分析记录"],
            ["RAG", "POST", "/api/rag/index/{file_id}", "重建该文件的检索索引"],
            ["RAG", "POST", "/api/rag/ask", "知识问答，返回答案与引用来源"],
            ["RAG", "GET", "/api/rag/history", "问答历史"],
            ["RAG", "GET", "/api/rag/chunks/{file_id}", "查看片段清单（调试用）"],
            ["Planner", "POST", "/api/planner/run", "自然语言分析：意图、事实、配图、回答"],
            ["Planner", "GET", "/api/planner/intents", "支持的意图类型与示例问题"],
            ["自动化", "GET", "/api/automation/rules", "规则列表"],
            ["自动化", "POST", "/api/automation/rules", "新建规则（校验目录存在）"],
            ["自动化", "PATCH", "/api/automation/rules/{id}", "修改规则（启停、目录、间隔）"],
            ["自动化", "DELETE", "/api/automation/rules/{id}", "删除规则"],
            ["自动化", "POST", "/api/automation/rules/{id}/scan", "立即扫描单条规则"],
            ["自动化", "POST", "/api/automation/scan", "立即扫描全部启用规则"],
            ["自动化", "GET", "/api/automation/runs", "自动化触发的分析记录"],
        ],
        widths=[2.0, 1.6, 6.6, 5.2],
        cap="表 4-1  接口清单",
    )

    h2(doc, "4.3  典型接口示例")
    h3(doc, "4.3.1  上传文件")
    code(
        doc,
        """POST /api/files/upload
Content-Type: multipart/form-data
files=sales_2024.csv
sheet=（可选，仅 Excel 指定工作表）

200 OK
{
  "count": 1,
  "files": [{
    "id": "23a022b2fbd948e0a8328718232dd968",
    "name": "sales_2024.csv",
    "rows": 906, "cols": 10, "status": "ready",
    "profile_preview": {
      "kind": "时间序列",
      "quality": {"score": 99.6, "grade": "A", "issues": []}
    },
    "warnings": []
  }]
}""",
    )

    h3(doc, "4.3.2  执行分析")
    body(doc, "请求参数：use_ai 控制是否调用模型，force 控制是否复用已有结果。响应包含画像、统计、"
              "图表数组与结论四部分，图表项中的 figure 字段可直接交给前端渲染。")
    code(
        doc,
        """POST /api/analysis/{file_id}/run?use_ai=true&force=false

200 OK（节选）
{
  "id": "eaf66720...", "status": "succeeded", "duration_ms": 237,
  "profile":  {"rows": 906, "cols": 10, "kind": "时间序列", "quality": {...}},
  "analysis": {"findings": [...], "correlations": {...}, "trend": {...}},
  "charts": [{
    "kind": "line", "title": "销售额 随时间变化",
    "reason": "检测到时间字段「订单日期」与数值指标「销售额」",
    "insight": "按月汇总后，销售额从 196.4k 到 115.0k，整体下降（-41.5%）",
    "figure": {"data": [...], "layout": {...}}
  }],
  "insights": {"engine": "llm", "summary": "...", "key_findings": [...]}
}""",
    )

    h3(doc, "4.3.3  知识问答")
    code(
        doc,
        """POST /api/rag/ask
{"question": "哪个地区的销售额最高？", "file_id": "23a022...", "k": 6}

200 OK
{
  "answer": "……华东……",
  "engine": "llm",
  "latency_ms": 1830,
  "sources": [
    {"title": "「地区」组间差异明显", "kind": "finding", "score": 0.4905}
  ]
}""",
    )

    h2(doc, "4.4  错误处理与降级策略")
    table(
        doc,
        ["场景", "系统行为", "用户感知"],
        [
            ["文件格式不支持", "上传即拒绝，返回 400 与支持列表", "红色错误提示，说明支持哪些后缀"],
            ["文件能存但不能解析", "保存文件并标记 failed，记录错误信息", "文件列表显示「失败」，可删除重传"],
            ["模型未配置", "结论、问答、规划走规则/检索兜底", "界面标注「规则兜底」"],
            ["模型调用超时或报错", "捕获异常、记录日志、返回兜底结果", "结果可用，标注降级原因"],
            ["向量索引失败", "回滚索引事务，不影响分析结果落库", "分析正常，问答可能提示无片段"],
            ["后端未启动", "前端捕获连接异常", "主页提示启动命令与端口"],
        ],
        widths=[3.4, 7.2, 4.8],
        cap="表 4-2  异常与降级策略",
    )


def chapter_5(doc: Document):
    h1(doc, "5  核心模块设计")

    h2(doc, "5.1  文件读取与类型推断")
    body(
        doc,
        "模块位置 backend/app/services/loader.py。目标是把「各种来源的表格」变成一份类型正确、列名干净的 "
        "DataFrame，同时记录读取过程（编码、分隔符、工作表、告警），供前端展示和问题排查。",
    )
    table(
        doc,
        ["处理环节", "策略"],
        [
            ["编码", "按 utf-8-sig → utf-8 → gb18030 → gbk → big5 → latin-1 依次尝试解码"],
            ["分隔符", "先用 csv.Sniffer 判断，失败时统计候选分隔符在每行出现的均值与方差，取最稳定者"],
            ["单列兜底", "若只解析出 1 列，说明分隔符可能猜错，换其它分隔符重试并取列数最多者"],
            ["表头定位", "Excel 中有过半列名为 Unnamed 时，扫描前 8 行按「文本数×2 + 唯一值数 + 非空数」打分选表头"],
            ["多工作表", "未指定时选择「行数×列数」最大的工作表，并记录全部表名"],
            ["空行空列", "删除全空行；仅在列名为自动生成（如「列3」）且全空时删除该列"],
            ["列名规范化", "去首尾空白、压缩连续空格、空名替换为「列N」、重名追加序号"],
        ],
        widths=[3.0, 12.4],
        cap="表 5-1  读取策略",
    )

    h3(doc, "5.1.1  类型推断顺序")
    body(
        doc,
        "CSV 统一以 dtype=str 读入，再由 infer_types 逐列判断，顺序为：布尔 → （列名含日期线索时）日期 → "
        "数值 → 日期 → 保留文本。先读字符串是为了避免 pandas 在解析阶段就把 \"001\" 变成 1，"
        "从而丢掉编号的前导零。",
    )
    table(
        doc,
        ["目标类型", "判定条件", "备注"],
        [
            ["布尔", "非空取值集合是 {是/否, true/false, 0/1, 对/错} 的子集且≤2 类", "统一转为可空布尔类型"],
            ["数值", "去掉千分位、货币与百分号后，≥95% 可转数字；且不像编号", "识别 1,200、12% 等常见写法"],
            ["日期", "抽样 200 行解析成功率≥90%；纯数字短串不视为日期", "支持 2024-01-01、2024/1/1 等混排"],
            ["文本", "以上均不满足", "保留原样，后续按唯一值比例区分维度/文本"],
        ],
        widths=[2.4, 9.4, 3.6],
        cap="表 5-2  类型推断规则",
    )
    body(
        doc,
        "编号保护规则：以 0 开头且长度大于 1 的数字串、以及长度≥12 的纯数字串，一律保留为文本，"
        "避免订单号、身份证号被转成数值后失真。",
    )

    h2(doc, "5.2  数据识别与质量评分")
    body(
        doc,
        "模块位置 profiler.py。识别结果是一个字典，包含行列规模、字段数组、语义角色分组、质量评分与摘要，"
        "前端「数据识别」页和后续的选图、拆解都消费这份画像。",
    )
    table(
        doc,
        ["角色", "判定规则", "典型字段"],
        [
            ["时间（time）", "字段已是日期类型", "订单日期、入职时间"],
            ["数值指标（measure）", "数值类型，且不是标识类字段", "销售额、月薪、评分"],
            ["分类维度（dimension）", "文本类型，唯一值 ≤ min(50, 行数×0.5)", "地区、品类、部门"],
            ["布尔标记（flag）", "布尔类型", "是否退货"],
            ["标识（id）", "名称含 id/编号/单号等；或唯一整数且从 0/1 开始连续", "订单号、员工编号"],
            ["文本（text）", "文本类型但唯一值过多", "备注、地址"],
        ],
        widths=[3.4, 8.4, 3.6],
        cap="表 5-3  语义角色判定",
    )
    body(doc, "质量评分从 100 分扣减，缺失、重复、常量列各占一部分权重，最终限制在 0–100：")
    code(
        doc,
        """score = 100
        - 整体缺失率 × 55
        - 重复行比例 × 25
        - (常量列数 / 总列数) × 20
score = clamp(score, 0, 100)

等级：A ≥ 90 ｜ B ≥ 75 ｜ C ≥ 60 ｜ D < 60""",
    )
    body(
        doc,
        "同时产出问题清单：缺失率>15%、存在重复行、存在常量列、样本量<30 都会生成对应条目并标注严重程度。",
    )

    h2(doc, "5.3  统计分析引擎")
    body(doc, "模块位置 analysis.py。围绕「看懂数据」组织五类分析，并把结论汇总成带分数的发现列表。")
    table(
        doc,
        ["分析项", "方法", "输出"],
        [
            ["描述统计", "计数、均值、中位数、标准差、四分位、偏度、零值占比", "指标统计表"],
            ["相关性", "皮尔逊相关系数，|r|≥0.4 才纳入，最多 8 个指标", "成对相关 + 热力矩阵"],
            ["时间趋势", "按跨度自动选择日/月/年粒度聚合，线性拟合得到斜率与 R²，计算首尾变化", "趋势序列与结论"],
            ["分组对比", "维度×指标聚合，取前 8 组，计算集中度与极差比", "分组明细"],
            ["异常值", "1.5×IQR 规则，统计超出区间个数与占比", "异常列清单"],
        ],
        widths=[2.6, 8.6, 4.2],
        cap="表 5-4  分析维度",
    )

    h3(doc, "5.3.1  关键发现的打分")
    table(
        doc,
        ["发现类型", "触发条件", "评分逻辑", "严重度"],
        [
            ["缺失", "单列缺失率≥20%", "55 + 缺失率×40", "≥70 高"],
            ["重复行", "重复比例>1%", "50", "中"],
            ["相关性", "|r|≥0.6", "60 + |r|×30", "高/中"],
            ["趋势", "首尾变化≥15%", "(52 或 58) + min(20, |变化率|/5)", "中"],
            ["集中度", "头部占比≥50% 且分组≥3", "50 + 占比×30", "中"],
            ["组间差异", "最大/最小≥3 倍", "52", "中"],
            ["异常值", "异常占比≥2%", "54", "中"],
            ["偏斜", "|偏度|≥1.5", "46", "低"],
            ["常量列", "唯一值≤1", "30", "低"],
        ],
        widths=[2.4, 5.2, 5.4, 2.4],
        cap="表 5-5  发现评分规则",
    )
    body(
        doc,
        "同类型发现最多保留 2 条，且按「类型 + 首个字段」去重，避免换个指标就把同一问题重复列出；"
        "最终按分数降序截取前 12 条。",
    )

    h3(doc, "5.3.2  趋势指标的选择")
    body(
        doc,
        "当多个指标都有时间序列时，选择「总量绝对值最大」的指标作为主趋势，而不是变化百分比最大的。"
        "否则一个基数很小的指标（例如销量 10→69）会用 +590% 的涨幅抢走主图，业务含义反而更弱。",
    )

    h2(doc, "5.4  图表推荐与生成")
    body(
        doc,
        "模块位置 charts.py。推荐器先生成候选（图表类型 + 字段组合 + 基础分），再按分数排序并施加约束，"
        "最后为每张图生成 Plotly JSON。",
    )
    table(
        doc,
        ["图表", "触发条件", "基础分", "用途"],
        [
            ["折线图", "存在时间字段 + 数值指标", "95 − 时间序号×8 − 指标序号×4", "看趋势"],
            ["柱状图", "分类维度（2–50 类）+ 数值指标", "86 − 维度序号×6 − 指标序号×4", "比大小"],
            ["饼图", "分类数≤6 且指标非负", "62 − 序号×4", "看占比结构"],
            ["散点图", "两数值指标 |r|≥0.5", "80 + |r|×10", "看关系与离群点"],
            ["热力图", "数值指标≥3 个", "72", "一屏看全部两两相关"],
            ["直方图", "存在数值指标", "66 − 序号×5", "看分布形态"],
            ["箱线图", "分类数≤8 + 数值指标", "58", "看组内离散与离群"],
            ["缺失率条形图", "整体缺失率>1%", "50", "定位问题字段"],
        ],
        widths=[2.8, 6.4, 3.6, 2.6],
        cap="表 5-6  图表候选与打分",
    )
    body(
        doc,
        "约束条件：同一类型最多 2 张、同一「类型+字段组合」不重复、总数默认 6 张。这样既保证主图优先，"
        "又不会六张全是柱状图。",
    )
    body(doc, "每张图最终交付的结构如下（figure 为 Plotly 图形 JSON，前端直接渲染）：")
    code(
        doc,
        """{
  "id": "line-1",
  "kind": "line",
  "title": "销售额 随时间变化",
  "reason": "检测到时间字段「订单日期」与数值指标「销售额」，趋势图最能体现变化",
  "insight": "按月汇总后，销售额从 196.4k 到 115.0k，整体下降（-41.5%）",
  "priority": 95,
  "columns": ["订单日期", "销售额"],
  "data": [{"period": "2024-01-01T00:00:00", "value": 196410.17}, ...],
  "figure": {"data": [...], "layout": {...}}
}""",
    )

    h2(doc, "5.5  AI 结论生成")
    body(
        doc,
        "模块位置 insights.py。输入是画像、统计结果与图表解读，输出是结构化的四段内容：整体结论、"
        "关键发现、建议动作、注意事项。",
    )
    h3(doc, "5.5.1  上下文压缩")
    body(
        doc,
        "为避免超长提示词与无关信息干扰，送模前做一次压缩：字段最多 25 个（每个只保留类型、关键统计、"
        "TOP3 取值、缺失率），相关性最多 5 对，发现最多 8 条，图表最多 6 条，总量控制在 6000 字符以内。",
    )
    h3(doc, "5.5.2  提示词结构")
    code(
        doc,
        """你是一名严谨的中文数据分析师。你会收到一份数据集的自动分析结果……
1. 只使用给定的事实和数字，禁止编造列名、数值或结论；
2. 语言简洁专业，面向不懂技术的业务同事；
3. 严格输出 JSON，不要输出任何多余文字。

JSON 结构：
{
  "summary": "80 字以内的整体结论",
  "key_findings": [{"title": "不超过 16 字", "detail": "一两句话，尽量带数字"}],
  "suggestions": ["可执行建议，2-4 条"],
  "caveats": ["数据局限或注意事项，1-3 条"]
}""",
    )
    h3(doc, "5.5.3  校验与降级")
    body(
        doc,
        "模型输出先做 JSON 提取（容忍 ```json 包裹与前后废话），再逐字段校验类型与长度；"
        "缺失字段用规则版内容补齐，多余字段丢弃。任何一步失败都返回规则结论，并在 insights.reason 中说明原因。"
        "规则版结论由发现列表 + 图表解读 + 固定建议模板拼装，保证「永远有输出」。",
    )

    h2(doc, "5.6  RAG 检索问答")
    body(
        doc,
        "模块位置 rag.py 与 embeddings.py。把一次分析拆成可检索的片段，问答时先检索再回答，并给出引用来源。",
    )
    table(
        doc,
        ["片段类型", "内容", "典型用途"],
        [
            ["dataset", "文件概览：规模、类型、质量、字段清单、5 行样例", "「这份数据是什么」"],
            ["quality", "质量与缺失：缺失字段及比例、重复行、质量问题", "「哪些字段有缺失」"],
            ["column", "单字段：类型、统计、TOP 取值、时间范围", "「销售额的分布」"],
            ["finding", "单条发现：标题、结论、涉及字段", "「哪个地区最强」"],
            ["chart", "单张图：标题、推荐理由、结论", "「这张图说明什么」"],
        ],
        widths=[2.6, 8.4, 4.4],
        cap="表 5-7  RAG 片段类型",
    )

    h3(doc, "5.6.1  向量化双模")
    body(
        doc,
        "默认使用本地哈希向量：对词级 token 与中文 bigram 做特征哈希，映射到 512 维并做 L2 归一化，"
        "无需下载模型、完全离线、结果确定。配置 EMBEDDING_MODEL 后改用 API 向量，二者对上层透明。",
    )

    h3(doc, "5.6.2  混合检索打分")
    body(doc, "召回阶段先取 3 倍候选，再按下面公式重排，最后取前 k 条：")
    code(
        doc,
        """score = 0.6 × 向量余弦相似度
      + 0.4 × 关键词重叠度（问题 token 在片段中的覆盖率）
      + 0.06 × 问题中点名的字段数（命中片段所属字段）

按 score 降序取 top-k（默认 6）""",
    )
    body(
        doc,
        "加入字段命中项后，「哪个地区的销售额最高」会稳定命中「地区」相关发现，而不是仅仅因为出现"
        "「销售额」三个字就召回渠道图。",
    )

    h3(doc, "5.6.3  问答流程")
    numbered(
        doc,
        [
            "把问题向量化，在指定文件（或全部文件）范围内检索 top-k 片段。",
            "把片段编号后拼进上下文，限制总长度 8000 字符。",
            "模型依据资料回答，并要求用 [编号] 标注引用；资料不足时明确说不知道。",
            "未配置模型时，直接返回片段要点（按标题 + 结论摘录），并提示配置 Key 后效果更好。",
            "问答记录与引用来源一并入库，便于追溯。",
        ],
    )

    h2(doc, "5.7  AI Planner")
    body(
        doc,
        "模块位置 planner.py。它解决的是「临时问题」：用户问一句「最近三个月销售额趋势怎么样」，"
        "系统需要判断意图、定位字段、现场计算并配图，而不是只返回已有结论。",
    )
    table(
        doc,
        ["意图", "关键词示例", "执行动作", "产出图"],
        [
            ["trend", "趋势、变化、走势、月度、同比", "按时间聚合指标，算环比与拟合", "折线图"],
            ["rank", "排名、最高、对比、哪个", "按维度聚合，取前 3 名", "柱状图"],
            ["distribution", "分布、集中、区间、波动", "统计分位数并计算直方", "直方图"],
            ["correlation", "相关、关系、影响", "取最强相关对并算 r", "散点图"],
            ["missing", "缺失、空值", "列出缺失最严重的字段", "缺失率图"],
            ["summary", "总结、概览、介绍", "汇总画像与主要发现", "推荐图 2 张"],
        ],
        widths=[2.6, 5.6, 5.0, 2.4],
        cap="表 5-8  Planner 意图体系",
    )
    body(
        doc,
        "执行流程：定位数据文件（显式指定 → 问题中出现文件名 → 最近上传）→ 读取并生成画像 → "
        "识别意图（有模型时由模型输出 JSON，否则按关键词打分）→ 在问题中匹配字段名 → "
        "执行对应计算并生成图表 → 有模型时组织成自然语言回答，否则输出要点列表。"
        "每一步都会记录到 steps 字段，前端可展开查看「执行计划」。",
    )

    h2(doc, "5.8  自动化执行")
    body(
        doc,
        "模块位置 automation.py。规则由「监视目录 + 文件匹配 + 是否启用 + 是否用 AI + 扫描间隔」构成，"
        "适用于每天落一份日报 CSV、希望自动出结论的场景。",
    )
    numbered(
        doc,
        [
            "后端启动时创建常驻协程，每隔一个扫描间隔（默认 60 秒）触发一轮扫描。",
            "扫描在线程中执行，避免阻塞事件循环；目录不存在或不可读时把错误写回规则。",
            "对匹配到的文件先算 SHA-256，已入库的文件直接跳过，保证重复扫描不会重复分析。",
            "新文件登记为文件记录（直接引用原路径，不复制），随后调用与分析接口相同的流水线。",
            "处理结果更新到规则的上次扫描时间、已处理数量与错误信息。",
        ],
    )
    body(
        doc,
        "幂等性由内容哈希保证：同一份文件无论扫描多少次，只会产生一条文件记录与一次分析。"
        "单轮单规则最多处理 20 个新文件，防止首次接入时目录积压导致长时间占用。",
    )

    h2(doc, "5.9  流水线编排与缓存")
    body(
        doc,
        "模块位置 pipeline.py。它把「读取 → 识别 → 分析 → 选图 → 出图 → 结论 → 落库 → 建索引」串起来，"
        "并处理三件事：解析缓存、结果复用、失败留痕。",
    )
    bullets(
        doc,
        [
            "解析缓存：以「文件 ID + SHA-256 + 工作表」为键缓存 DataFrame，最多 6 份，避免同一文件反复读盘。",
            "结果复用：若已有成功记录且 use_ai 参数一致，直接返回旧结果；force=true 时强制重算。",
            "失败留痕：异常时仍写入一条 failed 记录并保存错误信息，前端可以看到失败原因，而不是空白页面。",
            "索引解耦：建索引失败只回滚索引事务，不影响分析结果入库，问答侧提示无片段即可。",
        ],
    )


def chapter_6(doc: Document):
    h1(doc, "6  数据模型")

    h2(doc, "6.1  实体关系")
    body(
        doc,
        "共 5 张业务表。文件是聚合根，一个文件对应多条分析记录；检索片段与问答记录通过 file_id 关联；"
        "自动化规则独立存在，触发产生的分析记录以 trigger='automation' 标记。",
    )
    code(
        doc,
        """files 1 ──── n analysis_runs
  │
  ├──── n rag_chunks      （file_id）
  └──── n rag_chats       （file_id，可为空表示跨文件问答）

automation_rules ──(触发)──> files ──> analysis_runs""",
    )

    h2(doc, "6.2  表结构")
    h3(doc, "6.2.1  文件表 files")
    table(
        doc,
        ["字段", "类型", "说明"],
        [
            ["id", "字符串(32)", "主键，uuid4 十六进制"],
            ["name", "字符串", "磁盘上的文件名"],
            ["original_name", "字符串", "上传时的原始文件名"],
            ["ext / mime", "字符串", "扩展名与 MIME 类型"],
            ["size_bytes", "整数", "文件大小"],
            ["sha256", "字符串(64)", "内容哈希，用于去重"],
            ["storage_path", "文本", "文件绝对路径（自动化场景指向原目录）"],
            ["sheet_name / sheet_names", "字符串 / JSON", "当前工作表与全部工作表"],
            ["rows / cols", "整数", "解析后的行列数"],
            ["status", "字符串", "uploaded / ready / analyzed / failed"],
            ["error", "文本", "解析失败原因"],
            ["columns_meta", "JSON", "字段画像数组（类型、角色、统计）"],
            ["created_at", "时间", "上传时间（UTC）"],
        ],
        widths=[4.2, 3.4, 7.8],
        cap="表 6-1  files 表",
    )

    h3(doc, "6.2.2  分析记录表 analysis_runs")
    table(
        doc,
        ["字段", "类型", "说明"],
        [
            ["id", "字符串(32)", "主键"],
            ["file_id", "字符串(32)", "外键 → files.id，级联删除"],
            ["status", "字符串", "pending / running / succeeded / failed"],
            ["trigger", "字符串", "manual / automation / api / index"],
            ["options", "JSON", "本次参数（use_ai、是否建索引）"],
            ["profile / analysis", "JSON", "数据画像、统计分析结果"],
            ["charts", "JSON 数组", "图表规格与 Plotly 图形"],
            ["insights", "JSON", "结论、发现、建议、注意事项与生成方式"],
            ["model", "字符串", "生成结论所用的模型名（规则兜底时为空）"],
            ["duration_ms", "整数", "耗时毫秒"],
            ["error", "文本", "失败原因"],
            ["created_at", "时间", "创建时间"],
        ],
        widths=[4.2, 3.4, 7.8],
        cap="表 6-2  analysis_runs 表",
    )

    h3(doc, "6.2.3  检索片段表 rag_chunks")
    table(
        doc,
        ["字段", "类型", "说明"],
        [
            ["id", "字符串(32)", "主键"],
            ["file_id", "字符串(32)", "所属文件（索引字段）"],
            ["run_id", "字符串(32)", "来源分析记录（可空）"],
            ["kind", "字符串", "dataset / quality / column / finding / chart"],
            ["title", "字符串", "片段标题，用于展示与引用"],
            ["content", "文本", "片段正文，直接送进模型上下文"],
            ["meta", "JSON", "附加信息：文件、字段列表、图表类型"],
            ["embedding", "文本", "向量 JSON 数组（跨库通用）"],
            ["dim", "整数", "向量维度"],
            ["embedding_vec", "vector", "仅 PostgreSQL + pgvector 时存在的原生向量列"],
            ["created_at", "时间", "创建时间"],
        ],
        widths=[4.2, 3.4, 7.8],
        cap="表 6-3  rag_chunks 表",
    )

    h3(doc, "6.2.4  问答记录表 rag_chats")
    table(
        doc,
        ["字段", "类型", "说明"],
        [
            ["id", "字符串(32)", "主键"],
            ["file_id", "字符串(32)", "限定文件时记录，跨文件问答为空"],
            ["question / answer", "文本", "问题与回答全文"],
            ["sources", "JSON", "引用来源：标题、类型、相似度"],
            ["engine", "字符串", "llm / local"],
            ["latency_ms", "整数", "端到端耗时"],
            ["created_at", "时间", "提问时间"],
        ],
        widths=[4.2, 3.4, 7.8],
        cap="表 6-4  rag_chats 表",
    )

    h3(doc, "6.2.5  自动化规则表（automation_rules）")
    table(
        doc,
        ["字段", "类型", "说明"],
        [
            ["id", "字符串(32)", "主键"],
            ["name", "字符串", "规则名称"],
            ["watch_dir", "文本", "监视目录绝对路径"],
            ["pattern", "字符串", "文件匹配模式，如 *.csv"],
            ["enabled", "布尔", "是否启用"],
            ["use_ai", "布尔", "自动分析时是否调用模型"],
            ["interval_seconds", "整数", "扫描间隔（10–86400 秒）"],
            ["last_run_at / last_scanned_at", "时间", "最近成功处理时间 / 最近扫描时间"],
            ["last_error", "文本", "最近一次错误"],
            ["processed_count", "整数", "累计处理文件数"],
            ["created_at", "时间", "创建时间"],
        ],
        widths=[4.2, 3.4, 7.8],
        cap="表 6-5  automation_rules 表",
    )

    h2(doc, "6.3  索引、级联与完整性")
    bullets(
        doc,
        [
            "索引：files.sha256 用于上传去重；analysis_runs.file_id、rag_chunks.file_id、rag_chats.file_id 用于按文件查询。",
            "级联：analysis_runs 对 files 声明 ON DELETE CASCADE，删除文件时分析记录同步删除。",
            "SQLite 外键：连接建立时执行 PRAGMA foreign_keys=ON，否则级联不会生效，会留下孤儿记录。",
            "防御性删除：删除文件的接口同时显式删除该文件的分析记录，避免历史库未开外键时残留数据。",
            "时区：时间统一以 UTC 存储，序列化时补上 +00:00，由前端转换为本地时间。",
        ],
    )

    h2(doc, "6.4  PostgreSQL + pgvector 切换")
    body(
        doc,
        "连接串以 postgresql 开头时，启动阶段会自动执行扩展与索引 DDL；任意一步失败则整体退回 JSON 向量 + "
        "numpy 余弦，功能不受影响，/api/health 的 vector_mode 会如实反映当前模式。",
    )
    code(
        doc,
        """CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE rag_chunks
  ADD COLUMN IF NOT EXISTS embedding_vec vector;

CREATE INDEX IF NOT EXISTS rag_chunks_vec_idx
  ON rag_chunks USING hnsw (embedding_vec vector_cosine_ops);""",
    )
    body(
        doc,
        "检索时使用余弦距离算子 <=> 排序并换算为相似度；插入片段时同步写入 embedding_vec，"
        "JSON 列继续保留，便于迁移与调试。",
    )


def chapter_7(doc: Document):
    h1(doc, "7  前端设计")

    h2(doc, "7.1  页面结构")
    table(
        doc,
        ["页面", "路径", "职责", "主要交互"],
        [
            ["主页", "page/DashBoard.py", "运行状态、核心指标、最近分析、系统信息", "查看最近结果、进入各功能页"],
            ["文件", "page/Files.py", "上传、列表、预览、删除、发起分析", "多文件上传、预览前 30 行"],
            ["数据分析", "page/DataAnalysis.py", "展示分析结果主页面", "选择文件、开关 AI、强制重算"],
            ["浏览历史", "page/History.py", "历史列表与详情回看", "按文件/状态筛选、导出、删除"],
            ["询问", "page/AskFiles.py", "知识问答与智能分析两种模式", "对话式提问、查看引用与执行计划"],
            ["自动化文件设置", "page/AutoMation.py", "规则 CRUD、立即扫描、运行记录", "启停开关、创建规则"],
        ],
        widths=[2.6, 5.0, 4.6, 3.2],
        cap="表 7-1  页面清单",
    )

    h2(doc, "7.2  交互流程")
    body(
        doc,
        "主路径是「上传 → 分析 → 阅读 → 留存」：",
    )
    numbered(
        doc,
        [
            "在文件页选择文件上传，后端解析后会返回行列数、识别类型与质量评分，立即给出反馈。",
            "在文件列表选择文件，可先预览前 30 行确认数据无误。",
            "点击「开始自动分析」，前端调用分析接口并把结果写入 session_state，随后跳转到分析页展示。",
            "分析页按「智能图表 / 关键发现 / 数据识别 / AI 结论 / 数据预览」五个标签组织，避免一屏信息过载。",
            "结果自动留档，可随时从历史页按文件或状态找回，也可导出 JSON 报告。",
        ],
    )

    h2(doc, "7.3  渲染组件")
    bullets(
        doc,
        [
            "图表渲染：把后端 figure JSON 交给 plotly.io.from_json 构造图形，按容器宽度自适应，不重复计算数据。",
            "指标卡：行数、字段数、缺失率、质量评分（含等级）、图表与发现数量。",
            "发现卡片：按严重度着色，展示标题、参考分、说明与涉及字段。",
            "结论区：整体结论、关键发现、建议动作、注意事项四段，并标注生成方式。",
            "时间显示：统一把 UTC 转成本地时区，避免出现「差 8 小时」。",
        ],
    )

    h2(doc, "7.4  异常与空状态")
    table(
        doc,
        ["场景", "页面表现"],
        [
            ["后端未启动", "主页给出启动命令与端口，其余页面提示无法连接"],
            ["没有文件", "显示引导卡片，一键跳转到上传页"],
            ["解析失败", "文件状态标红，展示错误信息，可删除重传"],
            ["分析失败", "展示失败原因，可重新分析"],
            ["没有匹配图表", "提示字段过少，并回退展示统计表"],
            ["问答无片段", "提示先上传并分析文件，或重建索引"],
        ],
        widths=[3.6, 11.8],
        cap="表 7-2  异常状态处理",
    )


def chapter_8(doc: Document):
    h1(doc, "8  部署与配置")

    h2(doc, "8.1  环境要求")
    table(
        doc,
        ["项目", "要求"],
        [
            ["操作系统", "Windows 10/11（当前验证环境）、macOS、Linux"],
            ["Python", "3.10 及以上，当前验证版本 3.13.15"],
            ["内存", "建议 4 GB 以上（pandas 处理大文件时占用较高）"],
            ["磁盘", "预留上传文件与数据库空间，单文件默认上限 50 MB"],
            ["浏览器", "Edge / Chrome / Firefox 等现代浏览器"],
            ["端口", "8000（后端）、8501（前端）需可用"],
            ["可选", "PostgreSQL 14+ 与 pgvector 扩展；OpenAI 兼容模型服务"],
        ],
        widths=[3.2, 12.2],
        cap="表 8-1  环境要求",
    )

    h2(doc, "8.2  安装与启动")
    body(doc, "首次安装依赖：")
    code(
        doc,
        """cd C:\\Users\\Administrator\\PycharmProjects\\PythonProject1
.\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt""",
    )
    body(doc, "启动后端（终端一）：")
    code(
        doc,
        """cd backend
$env:PYTHONPATH="C:\\Users\\Administrator\\PycharmProjects\\PythonProject1\\backend"
..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --port 8000""",
    )
    body(doc, "启动前端（终端二）：")
    code(
        doc,
        """cd front
..\\.venv\\Scripts\\python.exe -m streamlit run app.py""",
    )
    body(
        doc,
        "更省事的方式：项目已内置两个 PyCharm 运行配置「后端 FastAPI (8000)」与「前端 Streamlit (8501)」，"
        "分别对应 backend/run_server.py 与 front/run_app.py，点击即可运行，无需手动设置 PYTHONPATH；"
        "也可以双击根目录的 run_dev.ps1 一次拉起两个窗口。",
    )

    h2(doc, "8.3  配置项说明")
    body(doc, "配置集中在项目根目录的 .env，由 pydantic-settings 读取，字段名不区分大小写。")
    table(
        doc,
        ["配置项", "默认值", "说明"],
        [
            ["DATABASE_URL", "sqlite:///…/data/app.db", "数据库连接串；以 postgresql 开头即启用 pgvector 逻辑"],
            ["OPENAI_API_KEY", "空", "模型密钥；为空则全部 AI 环节走兜底"],
            ["OPENAI_BASE_URL", "空", "中转/自建服务地址，需包含 /v1"],
            ["LLM_MODEL", "gpt-4o-mini", "模型名称，按服务方支持的名称填写"],
            ["LLM_TIMEOUT", "60", "单次调用超时秒数"],
            ["USE_AI_INSIGHTS", "true", "是否默认启用模型生成结论"],
            ["EMBEDDING_MODEL", "空", "留空使用本地哈希向量；填写后调用 API 向量"],
            ["EMBEDDING_DIM", "512", "本地哈希向量维度"],
            ["MAX_UPLOAD_MB", "50", "单文件上传上限"],
            ["AUTOMATION_INTERVAL_SECONDS", "60", "自动化扫描间隔"],
        ],
        widths=[5.4, 3.6, 6.4],
        cap="表 8-2  配置项",
    )
    code(
        doc,
        """# .env 示例
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=
EMBEDDING_DIM=512
MAX_UPLOAD_MB=50""",
    )

    h2(doc, "8.4  迁移到 PostgreSQL")
    numbered(
        doc,
        [
            "在数据库实例上执行 scripts/init_pg.sql，创建库与 vector 扩展。",
            "安装驱动：pip install \"psycopg[binary]\" pgvector。",
            "修改 .env 的 DATABASE_URL 为 postgresql+psycopg://用户:密码@主机:5432/ai_auto。",
            "重启后端，启动日志会提示后端已启动；访问 /api/health 确认 vector_mode 为 pgvector。",
            "对已有文件逐个调用 /api/rag/index/{file_id} 重建索引（或重新分析一次）。",
        ],
    )
    body(
        doc,
        "若扩展未安装或建列失败，系统会自动退回 numpy 余弦检索，不影响使用，只是检索性能与规模受限。",
    )

    h2(doc, "8.5  数据文件说明")
    table(
        doc,
        ["路径", "内容", "是否可删"],
        [
            ["data/app.db", "SQLite 数据库（文件、分析、片段、规则）", "删除即清空历史，需谨慎"],
            ["data/uploads/<随机>/", "上传文件副本", "可删，但对应文件记录会失效"],
            ["data/samples/", "自动生成的示例数据", "可删，可用脚本重建"],
            ["data/reports/", "预留的报告输出目录", "可删"],
            ["front/.streamlit/config.toml", "主题、上传大小、隐藏统计上报", "可改"],
        ],
        widths=[6.2, 6.4, 2.8],
        cap="表 8-3  数据文件",
    )


def chapter_9(doc: Document):
    h1(doc, "9  测试与验证")

    h2(doc, "9.1  测试策略")
    body(
        doc,
        "采用三层验证：服务层单元测试（纯函数，不依赖网络）、接口层端到端测试（FastAPI TestClient + "
        "临时 SQLite）、页面层渲染测试（Streamlit AppTest），最后用真实浏览器截图做视觉确认。"
        "测试使用独立数据库，不会污染 data/app.db。",
    )

    h2(doc, "9.2  用例分布")
    table(
        doc,
        ["测试文件", "用例数", "覆盖点"],
        [
            ["test_loader.py", "6", "编码探测、分隔符、前导零编号、千分位与百分号、空行、多工作表、格式拒绝"],
            ["test_profiler.py", "6", "角色识别、质量评分、常量列、标识列、时间范围、JSON 清洗"],
            ["test_analysis.py", "9", "相关性、趋势选择、分组、图表推荐与多样性、图表序列化、规则结论"],
            ["test_api.py", "11", "健康检查、上传去重、预览、分析、历史、RAG、Planner、统计、级联删除、自动化规则"],
        ],
        widths=[3.8, 2.2, 9.4],
        cap="表 9-1  测试用例分布（共 32 例）",
    )
    body(
        doc,
        "此外，六个页面均通过 Streamlit AppTest 执行（0 异常），并对「开始分析」「预览」「提问」等关键交互"
        "做了点击验证。",
    )

    h2(doc, "9.3  端到端实测")
    table(
        doc,
        ["数据集", "规模", "分析耗时", "产出"],
        [
            ["sales_2024.csv", "906 行 × 10 列", "约 0.4 秒", "6 张图、9 条发现、质量分 99.6（A）"],
            ["employees.xlsx", "260 行 × 9 列（2 工作表）", "约 0.2 秒", "6 张图、7 条发现、质量分 99.6（A）"],
        ],
        widths=[4.2, 5.0, 3.0, 6.2],
        cap="表 9-2  实测结果（未启用模型）",
    )
    body(
        doc,
        "自动化链路实测：在临时目录放入一份新 CSV，创建规则并触发扫描，成功产出 trigger=automation 的分析记录；"
        "再次扫描相同内容被哈希跳过，验证了幂等性。",
    )

    h2(doc, "9.4  已知问题与限制")
    table(
        doc,
        ["问题", "影响", "建议"],
        [
            ["当前 .env 中的模型 Key 已过期（401）", "AI 结论、问答、规划走兜底，界面标注「规则兜底」", "更换有效 Key 即可，无需改代码"],
            ["本地哈希向量的语义能力有限", "问答召回偏字面，复杂问法效果一般", "配置 EMBEDDING_MODEL 使用 API 向量"],
            ["分析为同步接口", "超大文件（数十万行）会长时间占用请求", "改为后台任务 + 轮询，或限制行数"],
            ["自动化采用轮询", "新文件最迟一个扫描间隔后才处理", "对时效要求高时改用文件系统事件"],
            ["单用户、无鉴权", "不适合直接暴露到公网", "如需多人使用，增加登录与按用户隔离数据"],
            ["仅分析首个（或最大）工作表", "多表关联场景需要手工拆分", "后续支持多表合并与关联分析"],
        ],
        widths=[4.4, 6.4, 5.6],
        cap="表 9-3  已知问题与限制",
    )


def chapter_10(doc: Document):
    h1(doc, "10  后续演进建议")

    h2(doc, "10.1  短期（1–2 周）")
    bullets(
        doc,
        [
            "接入有效模型 Key，用真实数据校准提示词与结论口径。",
            "分析改为后台任务：提交后返回任务 ID，前端轮询进度，避免长请求超时。",
            "补充失败重试与更细的错误码，前端按错误类型给出不同引导。",
            "增加批量分析：一次选择多个文件，排队执行并汇总结果。",
        ],
    )

    h2(doc, "10.2  中期（1–2 个月）")
    bullets(
        doc,
        [
            "多用户与权限：登录、按用户隔离文件与分析记录，支持分享链接。",
            "定时报表：按日/周自动分析指定文件并推送摘要（邮件或企业微信）。",
            "导出增强：除 JSON 外支持导出 Excel 汇总与带图 PDF。",
            "多工作表与多文件关联：支持主外键关联后的联合分析。",
        ],
    )

    h2(doc, "10.3  长期")
    bullets(
        doc,
        [
            "指标语义层：把「销售额」「毛利率」等口径沉淀为可复用指标定义，避免每次重复计算。",
            "接入更多数据源：数据库直连、对象存储、接口拉取，弱化「必须上传文件」的限制。",
            "可观测性：记录每次分析的输入摘要、耗时、模型调用与失败原因，形成质量看板。",
            "结论反馈闭环：允许用户对结论点赞/纠错，用于优化提示词与规则权重。",
        ],
    )


def appendix(doc: Document):
    h1(doc, "附录 A  项目目录结构")
    code(
        doc,
        """PythonProject1/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                FastAPI 入口、生命周期、自动化协程
│  │  ├─ core/                 配置、数据库、pgvector 初始化
│  │  ├─ models.py             5 张表的 ORM 模型
│  │  ├─ schemas.py            请求体模型
│  │  ├─ serializers.py        ORM 到 dict 的转换
│  │  ├─ services/
│  │  │  ├─ loader.py          CSV/Excel 读取与类型推断
│  │  │  ├─ profiler.py        字段角色与质量评分
│  │  │  ├─ analysis.py        统计分析与发现
│  │  │  ├─ charts.py          图表推荐与 Plotly 生成
│  │  │  ├─ insights.py        AI 结论与规则兜底
│  │  │  ├─ embeddings.py      哈希向量 / API 向量
│  │  │  ├─ rag.py             索引、检索、问答
│  │  │  ├─ planner.py         自然语言分析
│  │  │  ├─ automation.py      目录监听与扫描
│  │  │  ├─ pipeline.py        流水线编排与缓存
│  │  │  ├─ llm.py             模型客户端封装
│  │  │  └─ storage.py         文件落盘与去重
│  │  └─ api/routes/           files / analysis / rag / planner / automation / system
│  ├─ scripts/                 示例数据生成、PostgreSQL 初始化 SQL
│  ├─ tests/                   32 个 pytest 用例
│  └─ requirements.txt
├─ front/
│  ├─ app.py                   st.navigation 多页入口
│  ├─ lib/api.py               后端客户端
│  ├─ lib/ui.py                结果渲染组件
│  ├─ page/                    六个页面
│  └─ .streamlit/config.toml   主题与上传限制
├─ data/                       数据库、上传副本、示例数据
├─ docs/                       本技术文档与图表
├─ .env / .env.example         运行配置
└─ run_dev.ps1                 一键启动脚本""",
    )

    h1(doc, "附录 B  示例数据说明")
    table(
        doc,
        ["数据集", "字段", "构造特点", "用途"],
        [
            [
                "sales_2024.csv",
                "订单日期、地区、品类、渠道、销售额、销量、折扣率、客户评分、是否退货、毛利率",
                "900 余行，覆盖全年；人为加入 6% 缺失、6 行重复、5 个极端销售额",
                "验证时间序列识别、趋势、分组集中度、异常值检测",
            ],
            [
                "employees.xlsx",
                "员工编号、部门、职级、城市、入职日期、司龄、月薪、绩效评分、年龄",
                "260 行、两个工作表；月薪与年龄存在真实相关；绩效缺失 18 行",
                "验证多工作表选择、标识列识别、相关性发现",
            ],
        ],
        widths=[3.2, 6.0, 5.4, 3.4],
        cap="表 B-1  示例数据",
    )
    body(
        doc,
        "重新生成示例数据：cd backend 后执行 python scripts/make_samples.py，文件会写入 data/samples/。",
    )

    doc.add_page_break()
    h1(doc, "附录 C  常用命令速查")
    code(
        doc,
        """# 安装依赖
.\\.venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt

# 启动后端
cd backend
..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --port 8000

# 启动前端
cd front
..\\.venv\\Scripts\\python.exe -m streamlit run app.py

# 运行测试
cd backend
..\\.venv\\Scripts\\python.exe -m pytest tests -q

# 生成示例数据
cd backend
..\\.venv\\Scripts\\python.exe scripts\\make_samples.py

# 接口文档
http://127.0.0.1:8000/docs""",
    )


def main():
    doc = Document()
    setup(doc)
    cover(doc)
    toc(doc)
    chapter_1(doc)
    chapter_2(doc)
    chapter_3(doc)
    chapter_4(doc)
    chapter_5(doc)
    chapter_6(doc)
    chapter_7(doc)
    chapter_8(doc)
    chapter_9(doc)
    chapter_10(doc)
    appendix(doc)

    doc.save(OUTPUT)
    print(f"已生成：{OUTPUT}")


if __name__ == "__main__":
    main()
