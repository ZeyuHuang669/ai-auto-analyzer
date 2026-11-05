"""把 blog.md 排成适合发表的博客稿（.docx）。

Markdown 是唯一内容源：改 blog.md 后重跑本脚本即可，docx 会跟着更新。
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "blog.md"
OUTPUT = HERE / "博客稿-我做了个自动分析系统.docx"

BODY_FONT = "宋体"
HEAD_FONT = "微软雅黑"
MONO_FONT = "Consolas"

INK = "1F2937"
TITLE_COLOR = "16324F"
H2_COLOR = "1F4E79"
H3_COLOR = "2F5D8C"
MUTED = "6B7280"
CODE_INLINE = "A03A3A"
BORDER = "D5DEEA"
QUOTE_BG = "F4F8FC"
CODE_BG = "F5F6F8"
TABLE_HEAD_BG = "EDF2F9"

INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")


# --------------------------------------------------------------------------- #
# Markdown 解析
# --------------------------------------------------------------------------- #
def parse_blocks(text: str) -> list[tuple[str, str | list]]:
    lines = text.splitlines()
    blocks: list[tuple[str, str | list]] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        s = raw.strip()

        if not s:
            i += 1
            continue

        if s == "---":
            blocks.append(("hr", ""))
            i += 1
            continue

        if s.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", "\n".join(buf)))
            continue

        if s.startswith("### "):
            blocks.append(("h3", s[4:].strip()))
            i += 1
            continue
        if s.startswith("## "):
            blocks.append(("h2", s[3:].strip()))
            i += 1
            continue
        if s.startswith("# "):
            blocks.append(("h1", s[2:].strip()))
            i += 1
            continue

        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            blocks.append(("quote", "\n".join(buf)))
            continue

        if s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in row):
                    rows.append(row)
                i += 1
            blocks.append(("table", rows))
            continue

        if s.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            blocks.append(("ul", items))
            continue

        if re.match(r"^\d+\.\s", s):
            items = []
            while i < n and re.match(r"^\d+\.\s", lines[i].strip()):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            blocks.append(("ol", items))
            continue

        m = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", s)
        if m:
            blocks.append(("image", (m.group(1), m.group(2))))
            i += 1
            continue

        # 普通段落：连续非空行合并
        buf = [s]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", ">", "- ", "|", "```", "![", "---"))
                    or re.match(r"^\d+\.\s", nxt)):
                break
            buf.append(nxt)
            i += 1
        blocks.append(("p", "".join(buf)))

    return blocks


# --------------------------------------------------------------------------- #
# 排版工具
# --------------------------------------------------------------------------- #
def set_run(run, *, font: str = BODY_FONT, size: float = 11, bold=None,
            color: str | None = None):
    run.font.name = font
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)
    rfonts.set(qn("w:eastAsia"), HEAD_FONT if font == MONO_FONT else font)


def add_inline(paragraph, text: str, *, size: float = 11, color: str = INK):
    """处理 **加粗** 与 `行内代码`。"""
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            run = paragraph.add_run(part[2:-2])
            set_run(run, size=size, bold=True, color=color)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            set_run(run, font=MONO_FONT, size=size - 1, color=CODE_INLINE)
        else:
            run = paragraph.add_run(part)
            set_run(run, size=size, color=color)


def shade(paragraph_or_cell, hex_color: str):
    if hasattr(paragraph_or_cell, "_p"):
        pr = paragraph_or_cell._p.get_or_add_pPr()
    else:
        pr = paragraph_or_cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    pr.append(shd)


def left_border(paragraph, color: str = "4C78A8", size: int = 18):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    el = OxmlElement("w:left")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), "10")
    el.set(qn("w:color"), color)
    pbdr.append(el)
    ppr.append(pbdr)


def setup(doc: Document):
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Cm(2.6)
    section.bottom_margin = Cm(2.4)
    section.left_margin = Cm(2.6)
    section.right_margin = Cm(2.6)

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(11)
    normal.paragraph_format.line_spacing = 1.75
    normal.paragraph_format.space_after = Pt(10)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), BODY_FONT)
    rfonts.set(qn("w:hAnsi"), BODY_FONT)
    rfonts.set(qn("w:eastAsia"), BODY_FONT)

    props = doc.core_properties
    props.title = "以后再有人甩给我一个 Excel 说“帮我看看”，我就把这个系统甩给他"
    props.subject = "AI 自动化文件处理系统 博客稿"
    props.author = "项目组"
    props.keywords = "Python;Streamlit;FastAPI;数据分析;自动化;AI"


# --------------------------------------------------------------------------- #
# 渲染
# --------------------------------------------------------------------------- #
def render_table(doc: Document, rows: list[list[str]]):
    if not rows:
        return
    cols = max(len(r) for r in rows)
    table = doc.add_table(rows=0, cols=cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    for idx, row_data in enumerate(rows):
        row = table.add_row()
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        if idx == 0:
            tbl_header = OxmlElement("w:tblHeader")
            tbl_header.set(qn("w:val"), "true")
            tr_pr.append(tbl_header)
        for c in range(cols):
            cell = row.cells[c]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            text = row_data[c] if c < len(row_data) else ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.line_spacing = 1.2
            if idx == 0:
                shade(cell, TABLE_HEAD_BG)
                run = p.add_run(text)
                set_run(run, font=HEAD_FONT, size=9.5, bold=True, color=H2_COLOR)
            else:
                add_inline(p, text, size=9.5)

    # 让整张表尽量不跨页：除最后一行外都跟下一行绑定
    for row in table.rows[:-1]:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.keep_with_next = True

    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def build():
    text = SOURCE.read_text(encoding="utf-8")
    blocks = parse_blocks(text)

    plain = re.sub(r"[#>*`\-|!\[\]()]", "", text)
    char_count = len(re.sub(r"\s", "", plain))
    minutes = max(1, round(char_count / 420))

    doc = Document()
    setup(doc)

    title_done = False
    lede_done = False

    for index, (kind, payload) in enumerate(blocks):
        if kind == "h1" and not title_done:
            title_done = True
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.2
            run = p.add_run(payload)
            set_run(run, font=HEAD_FONT, size=21, bold=True, color=TITLE_COLOR)

            meta = doc.add_paragraph()
            meta.paragraph_format.space_after = Pt(18)
            run = meta.add_run(
                f"{date.today():%Y 年 %m 月 %d 日}  ·  约 {char_count:,} 字  ·  "
                f"阅读约 {minutes} 分钟"
            )
            set_run(run, font=HEAD_FONT, size=9, color=MUTED)
            continue

        if kind == "quote":
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.45)
            pf.right_indent = Cm(0.3)
            pf.space_before = Pt(6 if lede_done else 4)
            pf.space_after = Pt(16 if not lede_done else 12)
            pf.line_spacing = 1.6
            left_border(p)
            shade(p, QUOTE_BG)
            size = 11.5 if not lede_done else 10.5
            color = "44515F" if not lede_done else "4A5568"
            lines = str(payload).split("\n")
            for i, line in enumerate(lines):
                add_inline(p, line, size=size, color=color)
                if i < len(lines) - 1:
                    p.add_run().add_break()
            lede_done = True
            continue

        if kind == "h2":
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.space_before = Pt(24)
            pf.space_after = Pt(8)
            pf.left_indent = Cm(0.15)
            pf.keep_with_next = True
            run = p.add_run(payload)
            set_run(run, font=HEAD_FONT, size=15, bold=True, color=H2_COLOR)
            continue

        if kind == "h3":
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.space_before = Pt(16)
            pf.space_after = Pt(6)
            pf.keep_with_next = True
            run = p.add_run(payload)
            set_run(run, font=HEAD_FONT, size=12.5, bold=True, color=H3_COLOR)
            continue

        if kind == "p":
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(10)
            add_inline(p, str(payload))
            # 表格前的引导语要和表格绑在一起；图片不绑，否则会把整段文字顶到下一页留出大片空白
            nxt = blocks[index + 1][0] if index + 1 < len(blocks) else ""
            if nxt == "table":
                p.paragraph_format.keep_with_next = True
            continue

        if kind == "ul":
            for item in payload:
                p = doc.add_paragraph()
                pf = p.paragraph_format
                pf.left_indent = Cm(0.65)
                pf.first_line_indent = Cm(-0.65)
                pf.space_after = Pt(5)
                pf.line_spacing = 1.65
                run = p.add_run("·  ")
                set_run(run, size=11, color=H2_COLOR, bold=True)
                add_inline(p, item)
            continue

        if kind == "ol":
            for i, item in enumerate(payload, 1):
                p = doc.add_paragraph()
                pf = p.paragraph_format
                pf.left_indent = Cm(0.75)
                pf.first_line_indent = Cm(-0.75)
                pf.space_after = Pt(5)
                pf.line_spacing = 1.65
                run = p.add_run(f"{i}.   ")
                set_run(run, size=11, color=H2_COLOR, bold=True)
                add_inline(p, item)
            continue

        if kind == "image":
            alt, src = payload
            path = (SOURCE.parent / src).resolve()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(str(path), width=Cm(14.4))
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.paragraph_format.space_after = Pt(16)
            run = cap.add_run(alt)
            set_run(run, font=HEAD_FONT, size=8.5, color=MUTED)
            continue

        if kind == "table":
            render_table(doc, payload)
            continue

        if kind == "code":
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.4)
            pf.space_before = Pt(4)
            pf.space_after = Pt(10)
            pf.line_spacing = 1.25
            shade(p, CODE_BG)
            lines = str(payload).split("\n")
            for i, line in enumerate(lines):
                run = p.add_run(line)
                set_run(run, font=MONO_FONT, size=9, color="2B3440")
                if i < len(lines) - 1:
                    run.add_break()
            continue

        if kind == "hr":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(18)
            p.paragraph_format.space_after = Pt(14)
            run = p.add_run("·  ·  ·")
            set_run(run, font=HEAD_FONT, size=11, color=MUTED)
            continue

    doc.save(OUTPUT)
    print(f"已生成：{OUTPUT}")
    print(f"字数约 {char_count}，阅读约 {minutes} 分钟")


if __name__ == "__main__":
    build()
