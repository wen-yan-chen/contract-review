"""按演示脚本补全整套配图：6 张已有图 + 9 张补充页。

复用 make_figures.py 的视觉组件，保证配色、字号、留白完全一致。
输出：D:\\contest-32\\docs\\deck.pptx
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# ---------------------------------------------------------------- 复用已有组件

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("figs", str(HERE / "make_figures.py"))
figs = importlib.util.module_from_spec(spec)
sys.modules["figs"] = figs
spec.loader.exec_module(figs)

PAL = figs.PAL
INK, SUB, NAVY, WHITE = figs.INK, figs.SUB, figs.NAVY, figs.WHITE
RGB = figs.RGBColor
RGBColor = figs.RGBColor
box, txt, put, arrow, panel = figs.box, figs.txt, figs.put, figs.arrow, figs.panel
head, footer, chip, down_arrow = figs.head, figs.footer, figs.chip, figs.down_arrow
W, H = figs.W, figs.H

OUT = Path(r"D:\contest-32\docs\deck.pptx")
SHOT = Path(r"D:\contest-32\docs\screenshot.png")


def alpha_fill(shape, rgb, pct: int):
    """半透明填充：pct 为不透明度百分比（0–100）。"""
    from lxml import etree
    from pptx.oxml.ns import qn

    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb
    solid = shape.fill.fore_color._xFill.find(qn("a:srgbClr"))
    if solid is not None:
        a = etree.SubElement(solid, qn("a:alpha"))
        a.set("val", str(int(pct * 1000)))
    shape.line.fill.background()
    figs.strip(shape)


def send_back(slide, shape):
    """把形状移到最底层（背景层）。"""
    sp = slide.shapes._spTree
    el = shape._element
    sp.remove(el)
    sp.insert(2, el)


def add_bg(slide, section: int | None = None):
    """背景层：柔光圆 + 左侧细条 + 底部章节进度条。"""
    # 右上柔光圆
    c1 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(10.2), Inches(-1.5),
                                Inches(5.2), Inches(5.2))
    alpha_fill(c1, PAL["blue"][1], 5)
    send_back(slide, c1)

    # 左下柔光圆
    c2 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(-1.9), Inches(5.4),
                                Inches(4.2), Inches(4.2))
    alpha_fill(c2, PAL["blue"][1], 4)
    send_back(slide, c2)

    if section is None:
        return

    names = ["背景", "配置", "数据", "使用", "测试", "前端", "架构", "收获"]
    gap = Inches(0.06)
    total = Inches(12.13)
    seg = int((total - gap * (len(names) - 1)) / len(names))
    x = Inches(0.6)
    y = Inches(7.24)
    for i, n in enumerate(names):
        active = (i == section)
        b = box(slide, x, y, seg, Inches(0.06) if not active else Inches(0.09),
                PAL["blue"][1] if active else RGBColor(0xE2, 0xE8, 0xF2),
                None, radius=0.5)
        send_back(slide, b)
        x += seg + gap


def s_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])

    # 右侧深色渐变块
    pane = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(8.55), 0, Inches(4.79), H)
    pane.fill.gradient()
    pane.fill.gradient_angle = 45
    stops = pane.fill.gradient_stops
    stops[0].color.rgb = PAL["blue"][1]
    stops[0].position = 0.0
    stops[1].color.rgb = RGBColor(0x00, 0x1F, 0x5C)
    stops[1].position = 1.0
    pane.line.fill.background()
    figs.strip(pane)

    # 大号水印数字（半透明，置于右侧留白）
    wm = txt(s, Inches(9.15), Inches(-0.35), Inches(4.4), Inches(3.6), "32",
             size=150, bold=True, color=RGBColor(0x3D, 0x7B, 0xFF))
    for p in wm.text_frame.paragraphs:
        for r in p.runs:
            r.font.color.rgb = RGBColor(0x3D, 0x7B, 0xFF)

    # 左下柔光
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(-2.4), Inches(4.6),
                           Inches(5.4), Inches(5.4))
    alpha_fill(c, PAL["blue"][1], 5)

    txt(s, Inches(0.95), Inches(1.62), Inches(7.4), Inches(0.26),
        "魔擎开发者激励 1 期 ｜ 课题 #32", size=10.5, bold=True, color=PAL["blue"][1])
    txt(s, Inches(0.95), Inches(2.0), Inches(7.3), Inches(1.0),
        "贷款合同审查助手", size=44, bold=True, color=INK)
    txt(s, Inches(0.95), Inches(2.95), Inches(7.2), Inches(0.75),
        ["上传合同 · 40 条规则逐条比对", "原文定位与可采纳的修改建议"],
        size=13.5, color=SUB, spacing=1.6)

    box(s, Inches(0.95), Inches(3.95), Inches(4.2), Inches(0.035), PAL["blue"][1], None,
        shape=MSO_SHAPE.RECTANGLE)

    txt(s, Inches(0.95), Inches(4.25), Inches(7.0), Inches(1.0),
        ["Nexent 智能体 + FastAPI 服务层 + 前端三栏", "docker compose up -d 一键复现"],
        size=10.5, color=SUB, spacing=1.8)

    # 右侧数据（三行，数字与标签分离排布）
    stats = [("40", "条审查规则"), ("28", "份评测合同"), ("2.6%", "误报率")]
    y = Inches(4.15)
    for num, label in stats:
        txt(s, Inches(9.05), y, Inches(1.55), Inches(0.5), num, size=24, bold=True,
            color=WHITE, align=PP_ALIGN.LEFT)
        txt(s, Inches(9.05), y + Inches(0.44), Inches(3.6), Inches(0.24), label,
            size=9, color=RGBColor(0xC8, 0xDC, 0xFF))
        y += Inches(0.76)

    txt(s, Inches(9.05), Inches(6.78), Inches(3.9), Inches(0.28),
        "[姓名] · [学校] ｜ 2026 年 11 月", size=8.5,
        color=RGBColor(0xB9, 0xD0, 0xF5))


def s_background(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "选题背景：人工审查慢，且容易漏「没写」的部分", "BACKGROUND",
         "合同 90–110 条，需逐条对照四类要求")

    left, right = Inches(0.6), Inches(7.15)
    cw = Inches(5.55)

    txt(s, left, Inches(1.62), cw, Inches(0.26), "现状", size=10, bold=True, color=SUB)
    txt(s, right, Inches(1.62), cw, Inches(0.26), "本方案", size=10, bold=True, color=PAL["blue"][1])

    rows_l = [
        ("逐条比对", "100 条条款 × 4 类要求，靠人眼过"),
        ("漏检集中在「缺失」", "未约定登记、未写金额、未写送达地址"),
        ("标准不一致", "同一份合同，不同审查人结论不同"),
    ]
    rows_r = [
        ("自动切分索引", "按「第X条」切分，建立字符级偏移"),
        ("逐条匹配规则", "40 条规则入库，智能体逐条判定"),
        ("结构化输出", "定位 / 等级 / 建议 / 依据 四项齐全"),
    ]

    y = Inches(2.0)
    for (t1, d1), (t2, d2) in zip(rows_l, rows_r):
        box(s, left, y, cw, Inches(1.02), PAL["gray"][0], PAL["gray"][1], radius=0.06)
        txt(s, left + Inches(0.22), y + Inches(0.14), cw - Inches(0.44), Inches(0.26), t1,
            size=11.5, bold=True, color=INK)
        txt(s, left + Inches(0.22), y + Inches(0.5), cw - Inches(0.44), Inches(0.4), d1,
            size=9.5, color=SUB, spacing=1.35)

        box(s, right, y, cw, Inches(1.02), PAL["blue"][0], PAL["blue"][1], radius=0.06)
        txt(s, right + Inches(0.22), y + Inches(0.14), cw - Inches(0.44), Inches(0.26), t2,
            size=11.5, bold=True, color=NAVY)
        txt(s, right + Inches(0.22), y + Inches(0.5), cw - Inches(0.44), Inches(0.4), d2,
            size=9.5, color=SUB, spacing=1.35)

        arrow(s, left + cw + Inches(0.18), y + Inches(0.36), Inches(0.6), Inches(0.3))
        y += Inches(1.18)

    bar = box(s, Inches(0.6), Inches(5.85), Inches(12.13), Inches(0.72),
              RGBColor(0xEA, 0xF1, 0xFE), PAL["blue"][1], radius=0.06)
    put(bar, ["目标：一份合同 40 秒内给出风险清单，每条都能落到原文某一句、某个规则编号",
              "评测口径：28 份合同 ｜ 约 2900 条条款 ｜ 75 条计分标注"],
        size=9.5, color=NAVY, spacing=1.45)
    footer(s, "来源：docs/TEST_REPORT.md")


def s_data(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "数据说明：八类数据资产与口径", "DATA",
         "全部自造，无真实企业与个人信息 ｜ 规模由 check_coverage.py 实测")

    rows = [
        ("合同原文", "data/samples/", "28 份 · 1,368 KB", "每份 90–110 条、约 1 万字，覆盖 8 个行业"),
        ("边界样本", "data/samples/boundary/", "11 组", "无编号 / 跨页 / 表格 / 扫描件 / 120 条超长"),
        ("条款切分", "data/clauses/", "2,789 条 · 30.4 万字", "平均 100 条/份、109 字/条，含字符偏移"),
        ("人工标注", "data/labels/", "147 条", "计分 75 条 + 主观提示 72 条"),
        ("数据划分", "data/labels/split.json", "20 / 8 / 4", "dev / holdout / clean，clean ⊂ dev"),
        ("规则库", "data/rules/rules.yaml", "40 条", "20 条客观判据（计分）+ 20 条主观权衡（仅提示）"),
        ("合规定式", "data/rules/compliant.yaml", "12.6 KB", "确定性闸门的「合规即否决」依据"),
        ("知识库", "data/kb/rules-full.md", "13,829 字符 · 34.4 KB", "上传后切分 13 个分块，供语义检索"),
    ]

    # 列位置与宽度
    cols = [Inches(0.6), Inches(2.3), Inches(5.35), Inches(8.55)]
    widths = [Inches(1.62), Inches(2.95), Inches(3.1), Inches(4.18)]

    top = Inches(1.6)
    head_h = Inches(0.44)
    row_h = Inches(0.45)
    total_w = sum(int(w) for w in widths)

    # 表头
    box(s, cols[0], top, total_w, head_h, PAL["blue"][0], PAL["blue"][1], radius=0.0,
        shape=MSO_SHAPE.RECTANGLE)
    for j, label in enumerate(["类别", "路径", "规模", "说明"]):
        txt(s, cols[j] + Inches(0.14), top + Inches(0.11), widths[j] - Inches(0.2),
            Inches(0.24), label, size=9, bold=True, color=NAVY)

    # 数据行
    y = top + head_h
    for i, (a, b, c, d) in enumerate(rows):
        fill = WHITE if i % 2 == 0 else RGBColor(0xF8, 0xFB, 0xFF)
        box(s, cols[0], y, total_w, row_h, fill, RGBColor(0xE4, 0xEA, 0xF2), radius=0.0,
            shape=MSO_SHAPE.RECTANGLE, lw=0.5)
        txt(s, cols[0] + Inches(0.14), y + Inches(0.12), widths[0] - Inches(0.2),
            Inches(0.24), a, size=9.5, bold=True, color=INK)
        txt(s, cols[1] + Inches(0.14), y + Inches(0.13), widths[1] - Inches(0.2),
            Inches(0.24), b, size=8.5, color=SUB)
        txt(s, cols[2] + Inches(0.14), y + Inches(0.12), widths[2] - Inches(0.2),
            Inches(0.24), c, size=9.5, bold=True, color=PAL["blue"][2])
        txt(s, cols[3] + Inches(0.14), y + Inches(0.13), widths[3] - Inches(0.2),
            Inches(0.24), d, size=8.5, color=SUB)
        y += row_h

    # 底部两条结论
    bar = box(s, Inches(0.6), Inches(5.85), Inches(6.05), Inches(0.72),
              RGBColor(0xEA, 0xF1, 0xFE), PAL["blue"][1], radius=0.06)
    put(bar, ["计分口径：75 条计分标注，20 条客观规则全部被使用（20/20）",
              "评测结果见下页（检出 100% / 误报 2.6%）"], size=9, color=NAVY, spacing=1.4)

    bar2 = box(s, Inches(6.8), Inches(5.85), Inches(5.93), Inches(0.72),
               PAL["red"][0], PAL["red"][1], radius=0.06)
    put(bar2, ["踩过的坑：早期每份合同只覆盖 8/40 条规则，",
               "模型如实报「未约定抵押登记」被判成误报，误报率虚高到 48%"],
        size=9, color=PAL["red"][2], spacing=1.4)

    footer(s, "来源：tools/check_coverage.py ｜ tools/validate_labels.py ｜ docs/数据说明.md")


def s_kb(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "向量知识库：配置项与取值", "VECTOR KB",
         "挂载于智能体 contract_review ｜ 本地向量化，不调用外部 API")

    rows = [
        ("知识库", "contract-rules", "1 份文档", "挂载于 contract_review，单智能体专属"),
        ("文档", "rules-full.md", "40 条 · 13,829 字符 · 34.4 KB", "四条信息：判定条件 / 合规定式 / 缺陷形态 / 已知误报"),
        ("分块", "13 个分块", "每块约 1 KB", "按规则分节切分，检索粒度为「单条规则」"),
        ("向量模型", "bge-m3", "1024 维", "部署在本地 Ollama，不依赖外部接口"),
        ("检索方式", "语义相似度", "Top-K 命中", "命中后返回该规则的判定条件，供模型比对"),
        ("合规定式", "不入知识库", "改写入提示词", "实测入库会抬高误报，见下方结论"),
        ("字段口径", "judge 字段", "20 计分 + 20 提示", "知识库与规则库一一对应，避免两处不一致"),
    ]

    cols = [Inches(0.6), Inches(2.0), Inches(4.5), Inches(8.2)]
    widths = [Inches(1.32), Inches(2.4), Inches(3.6), Inches(4.53)]
    top = Inches(1.6)
    head_h = Inches(0.44)
    row_h = Inches(0.46)
    total_w = sum(int(w) for w in widths)

    box(s, cols[0], top, total_w, head_h, PAL["green"][0], PAL["green"][1], radius=0.0,
        shape=MSO_SHAPE.RECTANGLE)
    for j, label in enumerate(["配置项", "取值", "规模 / 参数", "说明"]):
        txt(s, cols[j] + Inches(0.14), top + Inches(0.11), widths[j] - Inches(0.2),
            Inches(0.24), label, size=9, bold=True, color=PAL["green"][2])

    y = top + head_h
    for i, (a, b, c, d) in enumerate(rows):
        fill = WHITE if i % 2 == 0 else RGBColor(0xF7, 0xFA, 0xFE)
        box(s, cols[0], y, total_w, row_h, fill, RGBColor(0xE4, 0xEA, 0xF2), radius=0.0,
            shape=MSO_SHAPE.RECTANGLE, lw=0.5)
        txt(s, cols[0] + Inches(0.14), y + Inches(0.13), widths[0] - Inches(0.2),
            Inches(0.24), a, size=9.5, bold=True, color=INK)
        txt(s, cols[1] + Inches(0.14), y + Inches(0.13), widths[1] - Inches(0.2),
            Inches(0.24), b, size=9, bold=True, color=PAL["green"][1])
        txt(s, cols[2] + Inches(0.14), y + Inches(0.13), widths[2] - Inches(0.2),
            Inches(0.24), c, size=9, color=INK)
        txt(s, cols[3] + Inches(0.14), y + Inches(0.14), widths[3] - Inches(0.2),
            Inches(0.24), d, size=8.5, color=SUB)
        y += row_h

    # 两条结论
    bar = box(s, Inches(0.6), Inches(5.35), Inches(5.95), Inches(1.0),
              RGBColor(0xEA, 0xF1, 0xFE), PAL["blue"][1], radius=0.06)
    put(bar, ["检索为什么用 13 块而不是 40 块",
              "按规则分节切分后，一次检索命中一条完整规则，不会跨规则拼接"],
        size=9, color=NAVY, spacing=1.4)

    bar2 = box(s, Inches(6.75), Inches(5.35), Inches(5.98), Inches(1.0),
               PAL["red"][0], PAL["red"][1], radius=0.06)
    put(bar2, ["一条被实测推翻的判断：合规定式最初也入库，误报 1 → 2 条",
               "检索按语义相似排序，反例与问题条款用词雷同，抬高该规则触发权重"],
        size=9, color=PAL["red"][2], spacing=1.4)

    footer(s, "来源：data/kb/rules-full.md ｜ Nexent 控制台知识库页")


def s_call(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "一次调用的实际开销与校验点", "PIPELINE COST", "单份 25–60 秒，均值 35 秒")

    steps = [("上传", "docx/pdf"), ("解析", "段落+表格"), ("切分", "第X条·偏移"),
             ("调智能体", "SSE 流"), ("过闸门", "确定性"), ("落盘", "JSON")]
    x = Inches(0.7)
    y = Inches(1.9)
    cw = Inches(1.85)
    gap = Inches(0.24)
    for i, (t, d) in enumerate(steps):
        c = box(s, x, y, cw, Inches(0.85), PAL["blue"][0], PAL["blue"][1], radius=0.08)
        put(c, [t, d], size=10.5, color=NAVY, spacing=1.3)
        c.text_frame.paragraphs[1].runs[0].font.size = Pt(8)
        c.text_frame.paragraphs[1].runs[0].font.color.rgb = SUB
        if i < 5:
            arrow(s, x + cw + Inches(0.03), y + Inches(0.3), Inches(0.18), Inches(0.24))
        x += cw + gap

    nums = [("blue", "≈1200", "流式事件", "一次调用的事件总数"),
            ("green", "3–4", "执行步骤", "解析 → 判定 → 成文"),
            ("amber", "35 秒", "平均耗时", "最长 60 秒")]
    x = Inches(0.7)
    for key, num, unit, desc in nums:
        panel(s, x, Inches(3.15), Inches(3.85), Inches(1.35), key)
        txt(s, x + Inches(0.25), Inches(3.3), Inches(2.0), Inches(0.55), num,
            size=24, bold=True, color=PAL[key][1])
        txt(s, x + Inches(2.3), Inches(3.4), Inches(1.4), Inches(0.26), unit,
            size=9.5, bold=True, color=PAL[key][2])
        txt(s, x + Inches(2.3), Inches(3.72), Inches(1.45), Inches(0.5), desc,
            size=8.5, color=SUB, spacing=1.25)
        x += Inches(4.03)

    panel(s, Inches(0.6), Inches(4.75), Inches(12.13), Inches(1.55), "red",
          "服务端的两个硬校验（不通过即丢弃该条）")
    txt(s, Inches(0.8), Inches(5.2), Inches(5.9), Inches(1.0),
        ["① 引用必须是条款原文的子串", "     模型只给引用，偏移由代码反查"],
        size=9.5, color=INK, spacing=1.5)
    txt(s, Inches(6.9), Inches(5.2), Inches(5.7), Inches(1.0),
        ["② clause_no 必须存在于切分结果中", "     防止模型编造条款号"],
        size=9.5, color=INK, spacing=1.5)

    footer(s, "来源：api/server.py ｜ api/nexent_client.py")


def s_iteration(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "误报率 38% → 2.6%：四阶段，每步都有验证", "ITERATION",
         "每次改动都跑全量 28 份合同，不留口头结论")

    steps = [
        ("初版", "38.0%", "边界模糊，跨条款推理多", "gray"),
        ("数据修复", "27.7%", "合规表述改为写明具体金额", "blue"),
        ("自证要求", "6.5%", "先复述判定条件并引用原文", "green"),
        ("确定性闸门", "2.6%", "两条定式固化为代码", "amber"),
    ]
    base_y = Inches(5.3)
    bw = Inches(2.55)
    gap = Inches(0.45)
    for i, (name, rate, desc, key) in enumerate(steps):
        x = Inches(0.7) + (bw + gap) * i
        h = Inches(1.3) + Inches(0.58) * i
        top = base_y - h
        box(s, x, top, bw, h, PAL[key][0], PAL[key][1], radius=0.04, lw=1.6)
        txt(s, x, top + Inches(0.14), bw, Inches(0.44), rate,
            size=21, bold=True, color=PAL[key][1], align=PP_ALIGN.CENTER)
        txt(s, x, top + Inches(0.62), bw, Inches(0.26), name,
            size=10, bold=True, color=INK, align=PP_ALIGN.CENTER)
        txt(s, x, base_y + Inches(0.12), bw, Inches(0.5), desc,
            size=8.5, color=SUB, align=PP_ALIGN.CENTER, spacing=1.3)
        if i < 3:
            arrow(s, x + bw + Inches(0.08), base_y - Inches(0.62), Inches(0.26),
                  Inches(0.22), key="gray")

    bar = box(s, Inches(0.7), Inches(5.85), Inches(11.94), Inches(0.62),
              PAL["red"][0], PAL["red"][1], radius=0.06)
    put(bar, "关键结论：模型的错误多是「套错规则」而非「编造」——所以要让它自证，而不是换更大的模型",
        size=9.5, color=PAL["red"][2])
    footer(s, "来源：docs/TEST_REPORT.md「优化记录」")


def s_ui(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "前端演示：三栏联动，四步走完一次审查", "FRONTEND",
         "对应录屏时间码：上传 → 筛选 → 四字段 → 比对导出")

    if SHOT.exists():
        pic_w = Inches(7.95)
        pic_h = int(pic_w * 1619 / 2590)
        left = Inches(0.6)
        top = Inches(1.62)
        s.shapes.add_picture(str(SHOT), left, top, width=pic_w, height=pic_h)
        box(s, left, top, pic_w, pic_h, None, PAL["gray"][1], radius=0.0, lw=0.75,
            shape=MSO_SHAPE.RECTANGLE)

        # 右侧四步
        rx = Inches(9.25)
        panel(s, rx, Inches(1.62), Inches(3.5), Inches(4.6), "blue", "录屏路径")
        steps = [
            ("0:00", "拖入合同", "状态条三行：解析中 / 已解析 106 条 / 完成 6 处"),
            ("0:25", "筛选与定位", "点「高」→ 点卡片，左栏自动滚动并高亮"),
            ("0:50", "四个字段", "原文 / 问题 / 建议 / 依据"),
            ("1:05", "比对与导出", "授信三项差异 → 导出 Word"),
        ]
        y = Inches(2.05)
        for t, name, desc in steps:
            txt(s, rx + Inches(0.22), y, Inches(0.55), Inches(0.24), t,
                size=8.5, bold=True, color=PAL["blue"][1])
            txt(s, rx + Inches(0.8), y - Inches(0.02), Inches(2.4), Inches(0.24), name,
                size=9.5, bold=True, color=INK)
            txt(s, rx + Inches(0.8), y + Inches(0.26), Inches(2.45), Inches(0.6), desc,
                size=8, color=SUB, spacing=1.3)
            y += Inches(1.0)

        # 图下注解
        txt(s, Inches(0.6), top + pic_h + Inches(0.07), Inches(8.1), Inches(0.24),
            "左栏合同列表可收起 ｜ 中间原文按字符偏移高亮 ｜ 右栏卡片与原文双向联动",
            size=8, color=SUB)
    else:
        txt(s, Inches(0.6), Inches(3), Inches(12), Inches(1),
            "缺少截图：docs/screenshot.png", size=12, color=SUB)

    footer(s, "来源：web/ ｜ 截图 docs/screenshot.png")


def s_gain(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "三点收获：关于模型、数据与边界", "TAKEAWAYS", "")

    items = [
        ("blue", "01", "模型的错误多是「套错规则」",
         ["复核 28 条误报，25 条不是编造，而是把问题挂到了最接近的规则号。",
          "解法是让它先自证判定条件，而不是换更大的模型——",
          "自证上线后误报 27.7% → 6.5%，检出只掉 1.3 个百分点。"]),
        ("green", "02", "数据集质量决定指标上限",
         ["早期每份合同只覆盖 8/40 条规则，模型如实报「未约定」却被判成误报，",
          "误报率虚高到 48%。补齐 40/40 覆盖后，同样的模型误报降到 27.7%。",
          "评测口径不干净，任何调优都不可信。"]),
        ("amber", "03", "把不确定性留在代码边界内",
         ["定位、切分、闸门、校验全部是确定性代码；模型只做语义判断。",
          "凡是能用规则判定的就不交给模型——可复现、可审计、可回滚。",
          "这也是定位准确率能到 100% 的原因。"]),
    ]

    x = Inches(0.6)
    cw = Inches(3.95)
    badges = ["误报 27.7% → 6.5%", "误报 48% → 27.7%", "定位准确率 100%"]
    for i, (key, num, title, lines) in enumerate(items):
        panel(s, x, Inches(1.55), cw, Inches(3.75), key)
        txt(s, x + Inches(0.28), Inches(1.72), Inches(1.0), Inches(0.4), num,
            size=18, bold=True, color=PAL[key][1])
        txt(s, x + Inches(0.28), Inches(2.12), cw - Inches(0.56), Inches(0.5), title,
            size=11.5, bold=True, color=INK, spacing=1.3)
        txt(s, x + Inches(0.28), Inches(2.72), cw - Inches(0.56), Inches(1.9), lines,
            size=9, color=SUB, spacing=1.55)
        b = box(s, x + Inches(0.28), Inches(4.6), cw - Inches(0.56), Inches(0.42),
                WHITE, PAL[key][1], radius=0.14)
        put(b, badges[i], size=9, bold=True, color=PAL[key][2])
        x += cw + Inches(0.22)

    bar = box(s, Inches(0.6), Inches(5.7), Inches(12.13), Inches(0.75),
              RGBColor(0xEA, 0xF1, 0xFE), PAL["blue"][1], radius=0.06)
    put(bar, ["可交付：28 份合同数据集 ｜ 40 条规则库 ｜ 4 个技能包 ｜ 一键部署 ｜ 测试报告与复现脚本",
              "六项指标：检出 100% ｜ 误报 2.6% ｜ 定位 100% ｜ 等级 100% ｜ 建议 96% ｜ 一致性 1.000"],
        size=9.5, color=NAVY, spacing=1.4)
    footer(s, "来源：docs/TEST_REPORT.md ｜ docs/DESIGN.md")


def s_end(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    box(s, 0, 0, Inches(0.3), H, PAL["blue"][1], None, shape=MSO_SHAPE.RECTANGLE)

    txt(s, Inches(1.15), Inches(2.0), Inches(10), Inches(0.3), "一句话总结",
        size=10.5, bold=True, color=PAL["blue"][1])
    txt(s, Inches(1.15), Inches(2.35), Inches(10.8), Inches(1.0),
        ["把 40 条审查规则，变成一次上传、40 秒、5 处提示。"],
        size=25, bold=True, color=INK, spacing=1.35)

    box(s, Inches(1.15), Inches(3.55), Inches(4.6), Inches(0.03), PAL["blue"][1], None,
        shape=MSO_SHAPE.RECTANGLE)

    rows = [("代码仓库", "[GitHub 地址]"), ("智能体", "AgentsHub PR #59"),
            ("部署", "docker compose up -d")]
    y = Inches(3.85)
    for k, v in rows:
        txt(s, Inches(1.15), y, Inches(1.4), Inches(0.3), k, size=9.5, color=SUB)
        txt(s, Inches(2.6), y, Inches(8), Inches(0.3), v, size=10, color=INK)
        y += Inches(0.4)


def s_toc(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])

    txt(s, Inches(0.9), Inches(0.82), Inches(6), Inches(0.5), "目录", size=38, bold=True, color=INK)
    txt(s, Inches(0.95), Inches(1.42), Inches(6), Inches(0.4), "CONTENTS", size=17, bold=True,
        color=PAL["blue"][1])

    items = [
        ("01", "选题背景", "人工审查的痛点与目标"),
        ("02", "应用配置", "智能体 · 模型 · 向量库 · 技能"),
        ("03", "数据说明", "8 类数据资产与评测口径"),
        ("04", "Nexent 使用过程", "知识库 · 提示词 · 调用链路"),
        ("05", "测试过程", "三步流程 · 指标 · 优化记录"),
        ("06", "前端演示", "三栏联动与四步操作"),
        ("07", "架构总结", "三层分工与六环节"),
        ("08", "项目收获", "三点结论"),
    ]

    col_x = [Inches(0.9), Inches(6.95)]
    row_h = Inches(1.04)
    for i, (num, name, desc) in enumerate(items):
        col, row = i // 4, i % 4
        x = col_x[col]
        y = Inches(2.1) + row_h * row

        txt(s, x, y, Inches(0.85), Inches(0.5), num, size=23, bold=True,
            color=PAL["blue"][1])
        txt(s, x + Inches(0.85), y + Inches(0.01), Inches(3.6), Inches(0.34), name,
            size=13.5, bold=True, color=INK)
        txt(s, x + Inches(0.85), y + Inches(0.38), Inches(3.9), Inches(0.3), desc,
            size=9, color=SUB)
        box(s, x + Inches(0.85), y + Inches(0.86), Inches(4.3), Inches(0.012),
            RGBColor(0xE4, 0xEA, 0xF2), None, shape=MSO_SHAPE.RECTANGLE)

    footer(s, "魔擎开发者激励 1 期 · 课题 #32 ｜ 贷款合同审查助手")


def s_shot(prs, img: Path, title, kicker, facts, note=None, max_w=7.2, max_h=4.95):
    """一张平台截图 + 右侧要点。"""
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, title, kicker)

    if img.exists():
        from PIL import Image

        iw, ih = Image.open(img).size
        scale = min(max_w / iw, max_h / ih)
        w = Inches(iw * scale)
        h = Inches(ih * scale)
        left = Inches(0.6)
        top = Inches(1.55) + (Inches(max_h) - h) // 2
        s.shapes.add_picture(str(img), left, top, width=w, height=h)
        box(s, left, top, w, h, None, RGBColor(0xD6, 0xDC, 0xE3), radius=0.0, lw=0.75,
            shape=MSO_SHAPE.RECTANGLE)

    # 右侧要点
    rx = Inches(8.25)
    ph = Inches(0.62) + Inches(0.43) * len(facts)
    panel(s, rx, Inches(1.55), Inches(4.5), ph, "blue", "关键配置")

    y = Inches(1.95)
    for k, v in facts:
        txt(s, rx + Inches(0.24), y, Inches(1.35), Inches(0.24), k, size=8.5, color=SUB)
        txt(s, rx + Inches(1.6), y - Inches(0.02), Inches(2.7), Inches(0.26), v,
            size=9.5, bold=True, color=INK)
        y += Inches(0.43)

    if note:
        bar = box(s, rx, Inches(1.55) + ph + Inches(0.22), Inches(4.5), Inches(1.15),
                  PAL["red"][0], PAL["red"][1], radius=0.06)
        put(bar, note, size=8.5, color=PAL["red"][2], spacing=1.45)

    footer(s, "来源：Nexent 控制台实拍")
    return s


def decorate(prs, sections: dict[int, int] | None = None):
    """统一装饰：背景光斑 + 底部分节进度条 + 右上徽标 + 页码。"""
    sections = sections or {}
    for i, s in enumerate(prs.slides):
        if i == 0:
            continue
        add_bg(s, sections.get(i))
        chip = box(s, W - Inches(2.05), Inches(0.44), Inches(1.05), Inches(0.28),
                   PAL["blue"][0], PAL["blue"][1], radius=0.45)
        put(chip, "课题 #32", size=8, bold=True, color=NAVY)
        txt(s, W - Inches(1.05), H - Inches(0.5), Inches(0.6), Inches(0.24),
            f"{i + 1:02d}", size=9, color=SUB, align=PP_ALIGN.RIGHT)


def main() -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    SHOTS = Path(r"D:\contest-32\docs\figures")

    s_cover(prs)
    s_toc(prs)
    s_background(prs)

    # 应用配置：四张截图 + 总览
    s_shot(prs, SHOTS / "智能体截图.png",
           "应用配置①：智能体与整体结构", "APPLICATION CONFIG 1 / 4",
           [("智能体名", "contract_review"), ("状态", "已发布"),
            ("模型", "deepseek-chat"), ("知识库", "contract-rules"), ("技能", "4 个")],
           note=["智能体是唯一入口：模型、知识库、技能三项",
                 "都在这里挂载，换模型不影响规则与前端"])
    s_shot(prs, SHOTS / "大语言模型截图.png",
           "应用配置②：大语言模型参数", "APPLICATION CONFIG 2 / 4",
           [("模型", "deepseek-chat"), ("temperature", "0"),
            ("max_steps", "15"), ("输出", "JSON schema"), ("单次耗时", "25–60 秒")],
           note=["温度设 0 是为了可复现：同一份合同连跑三次，",
                 "风险集合必须完全一致（一致性 Jaccard = 1.000）"])
    s_shot(prs, SHOTS / "向量模型截图.png",
           "应用配置③：向量模型与知识库", "APPLICATION CONFIG 3 / 4",
           [("向量模型", "bge-m3"), ("维度", "1024"),
            ("部署", "本地 Ollama"), ("文档", "34.4 KB / 40 条"), ("分块", "13 个")],
           note=["向量模型本地部署，不调用外部 API；",
                 "bge-m3 对中文长句的语义区分优于通用模型"])
    s_shot(prs, SHOTS / "skills截图.jpg",
           "应用配置④：四个自定义技能", "APPLICATION CONFIG 4 / 4",
           [("loan-rule-cards", "知识类"), ("missing-clause-audit", "流程类"),
            ("risk-selfcheck", "流程类"), ("suggestion-compiler", "流程类"),
            ("目标指标", "四项各一")],
           note=["导入顺序：先装 4 个 Skill，再导入 agent.json；",
                 "顺序反了平台会报依赖缺失"])

    figs.fig1(prs)

    s_data(prs)
    s_kb(prs)

    figs.fig2(prs)
    figs.fig3(prs)
    s_call(prs)

    figs.fig4(prs)
    figs.fig5(prs)
    s_iteration(prs)

    s_ui(prs)
    figs.fig6(prs)
    s_gain(prs)
    s_end(prs)

    # 章节归属（0 基页序）：背景 0 / 配置 1 / 数据 2 / 使用 3 / 测试 4 / 前端 5 / 架构 6 / 收获 7
    sections = {2: 0, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1,
                8: 2, 9: 3, 10: 3, 11: 3, 12: 3,
                13: 4, 14: 4, 15: 4, 16: 5, 17: 6, 18: 7}
    decorate(prs, sections)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"已生成 {len(prs.slides)} 页 → {OUT}")


if __name__ == "__main__":
    main()
