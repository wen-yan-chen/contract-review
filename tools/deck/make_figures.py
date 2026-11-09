"""按美赛流程图模板的视觉规则，生成 6 张项目配图。

风格来源（模板实测）：
  画布 13.33×7.5；浅色大面板填充（#EDF7FF / #F0F8ED / #FFF9E5 / #FDEDEC / #F4EEFA）；
  面板描边 1pt；面板内小方块；箭头用实心色块；标题深蓝 #1F4E78。

输出：D:\\contest-32\\docs\\figures.pptx（6 页）
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

W, H = Inches(13.333), Inches(7.5)
OUT = Path(r"D:\contest-32\docs\figures.pptx")

INK = RGBColor(0x1A, 0x22, 0x2E)
SUB = RGBColor(0x5A, 0x67, 0x78)
NAVY = RGBColor(0x00, 0x2B, 0x6B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PRIMARY = RGBColor(0x00, 0x63, 0xFF)
LINE_GRAY = RGBColor(0xD6, 0xDC, 0xE3)

# 单色蓝阶：(浅填充, 描边, 强调) —— 色相统一 216°，仅明度/饱和度递减
PAL = {
    "blue":   (RGBColor(0xE9, 0xF1, 0xFF), RGBColor(0x00, 0x63, 0xFF), RGBColor(0x00, 0x43, 0xA8)),
    "green":  (RGBColor(0xE4, 0xEC, 0xFB), RGBColor(0x2F, 0x63, 0xC8), RGBColor(0x00, 0x3A, 0x8F)),
    "amber":  (RGBColor(0xEF, 0xF4, 0xFD), RGBColor(0x5C, 0x86, 0xD6), RGBColor(0x1F, 0x45, 0x94)),
    "red":    (RGBColor(0xD8, 0xE2, 0xF5), RGBColor(0x00, 0x2B, 0x6B), RGBColor(0x00, 0x1E, 0x4E)),
    "purple": (RGBColor(0xEC, 0xF1, 0xFB), RGBColor(0x46, 0x67, 0xB5), RGBColor(0x1A, 0x35, 0x6E)),
    "gray":   (RGBColor(0xF6, 0xF7, 0xF9), RGBColor(0xC9, 0xD1, 0xDA), RGBColor(0x3A, 0x46, 0x53)),
}

FONT = "黑体"


def strip(shape):
    from lxml import etree
    from pptx.oxml.ns import qn

    el = shape._element
    st = el.find(qn("p:style"))
    if st is not None:
        el.remove(st)
    spPr = el.spPr
    if spPr.find(qn("a:effectLst")) is None:
        etree.SubElement(spPr, qn("a:effectLst"))


def box(slide, x, y, w, h, fill, line=None, radius=0.04, lw=1.0,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            s.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(lw)
    strip(s)
    s.text_frame.word_wrap = True
    return s


def txt(slide, x, y, w, h, lines, size=12, bold=False, color=INK,
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.25):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    content = lines if isinstance(lines, list) else [lines]
    for i, line in enumerate(content):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run()
        r.text = line
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
    return tb


def put(shape, lines, size=12, bold=False, color=INK, align=PP_ALIGN.CENTER, spacing=1.15):
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.06)
    tf.margin_right = Inches(0.06)
    tf.margin_top = 0
    tf.margin_bottom = 0
    content = lines if isinstance(lines, list) else [lines]
    for i, line in enumerate(content):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run()
        r.text = line
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color


def arrow(slide, x, y, w, h, key="blue"):
    s = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = PAL[key][1]
    s.line.fill.background()
    strip(s)
    return s


def down_arrow(slide, x, y, w, h, key="blue"):
    s = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = PAL[key][1]
    s.line.fill.background()
    strip(s)
    return s


def head(slide, cn, en, sub=None):
    txt(slide, Inches(0.6), Inches(0.3), Inches(9), Inches(0.24), en,
        size=10, bold=True, color=PAL["blue"][1])
    txt(slide, Inches(0.6), Inches(0.5), Inches(11.2), Inches(0.5), cn,
        size=24, bold=True, color=INK)
    if sub:
        txt(slide, Inches(0.6), Inches(1.02), Inches(11.8), Inches(0.24), sub,
            size=11, color=SUB)


def footer(slide, text):
    txt(slide, Inches(0.6), Inches(7.0), Inches(12.1), Inches(0.24), text,
        size=8.5, color=SUB)


def panel(slide, x, y, w, h, key, title=None, note=None):
    fill, line, accent = PAL[key]
    box(slide, x, y, w, h, fill, line, lw=1.0)
    if title:
        txt(slide, x + Inches(0.18), y + Inches(0.12), w - Inches(0.3), Inches(0.26),
            title, size=12, bold=True, color=accent)
    if note:
        txt(slide, x + Inches(0.18), y + h - Inches(0.36), w - Inches(0.3), Inches(0.24),
            note, size=9, color=SUB)
    return (x, y, w, h)


def chip(slide, x, y, w, h, text, key="blue", size=10.5, bold=False):
    fill, line, accent = PAL[key]
    s = box(slide, x, y, w, h, WHITE, line, lw=0.9)
    put(s, text, size=size, bold=bold, color=accent)
    return s


# ---------------------------------------------------------------- 图 1 应用配置并列


def fig1(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "应用配置：四项能力并列支撑同一次审查", "APPLICATION CONFIGURATION",
         "智能体 contract_review ｜ 已发布 ｜ 版本 1")

    cols = [
        ("blue", "大模型", "deepseek-chat",
         ["温度 0（同输入同结果）", "最大步数 15", "单次 25–60 秒，均值 35 秒"]),
        ("green", "向量知识库", "contract-rules",
         ["34.4 KB · 40 条规则", "切分 13 个分块", "bge-m3 · 1024 维"]),
        ("amber", "自定义技能", "4 个 Skill",
         ["规则卡片 · 缺失审计", "输出自检 · 建议编译", "各对应一项指标"]),
        ("purple", "系统提示词", "2942 字符",
         ["七段结构", "判定闸门 + 自证要求", "合规写法禁止上报"]),
    ]

    x0, y0 = Inches(0.6), Inches(1.62)
    cw, ch, gap = Inches(2.95), Inches(3.55), Inches(0.2)

    for i, (key, title, sub, items) in enumerate(cols):
        x = x0 + (cw + gap) * i
        panel(s, x, y0, cw, ch, key, title)
        # 副标题条
        bar = box(s, x + Inches(0.18), y0 + Inches(0.5), cw - Inches(0.36), Inches(0.34),
                  PAL[key][1], None, radius=0.12)
        put(bar, sub, size=9.5, bold=True, color=WHITE)

        yy = y0 + Inches(1.02)
        for it in items:
            c = box(s, x + Inches(0.18), yy, cw - Inches(0.36), Inches(0.62),
                    WHITE, PAL[key][1], radius=0.08)
            put(c, it, size=10, color=PAL[key][2], align=PP_ALIGN.LEFT)
            c.text_frame.margin_left = Inches(0.12)
            yy += Inches(0.72)

    # 底部汇总条
    bar = box(s, Inches(0.6), Inches(5.55), Inches(12.13), Inches(0.78),
              RGBColor(0xEA, 0xF1, 0xFE), PAL["blue"][1], radius=0.06)
    put(bar, ["四项配置共同决定结果质量：模型定可复现，知识库定判定依据，技能定指标上限，提示词定误报",
              "配置均可复现：agent.json 导出 + skills/*.zip + rules-full.md 三份材料"],
        size=10.5, color=NAVY, spacing=1.5)

    footer(s, "来源：Nexent 控制台 · agent/agent.json · data/kb/rules-full.md")
    return s


# ---------------------------------------------------------------- 图 2 提示词流程


def fig2(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "提示词结构：七段串联，两段决定误报率", "PROMPT PIPELINE",
         "系统提示词 2942 字符 ｜ 逐段向下生效")

    steps = [
        ("角色与视角", "服务对象 · 出借人立场", "gray"),
        ("审查范围", "40 条规则 · 以知识库为准", "gray"),
        ("输出格式", "强制 JSON schema", "gray"),
        ("硬性约束", "引用逐字 · 依据禁编造", "blue"),
        ("判定闸门", "合规写法禁报 · 禁引入未列明判据", "red"),
        ("判定边界", "禁跨条款推理 · 缺失须全文确认", "blue"),
        ("自证要求", "先复述判定条件再报，做不到即删除", "red"),
    ]

    x_left = Inches(0.75)
    w = Inches(6.5)
    y = Inches(1.5)
    hgt = Inches(0.6)
    gap = Inches(0.13)

    for i, (t, d, key) in enumerate(steps):
        fill, line, accent = PAL[key]
        b = box(s, x_left, y, w, hgt, fill, line, radius=0.06,
                lw=2.2 if key == "red" else 1.0)
        txt(s, x_left + Inches(0.18), y + Inches(0.07), Inches(2.05), Inches(0.24),
            f"{i + 1:02d}  {t}", size=11, bold=True, color=accent)
        txt(s, x_left + Inches(2.3), y + Inches(0.09), w - Inches(2.45), Inches(0.42),
            d, size=10, color=SUB)
        if i < len(steps) - 1:
            down_arrow(s, x_left + w / 2 - Inches(0.1), y + hgt + Inches(0.01),
                       Inches(0.2), Inches(0.11), key="gray")
        y += hgt + gap

    # 右侧说明
    rx = Inches(7.55)
    panel(s, rx, Inches(1.5), Inches(5.2), Inches(2.28), "red", "判定闸门：写「什么不算问题」")
    txt(s, rx + Inches(0.2), Inches(1.86), Inches(4.8), Inches(1.8),
        ["· 四种合规写法一律不得报告",
         "· 未列入规则库的判据不得引入",
         "· 「可以更完善」不属于风险",
         "· 闸门必须在提示词内，不能放知识库",
         "   ——检索按语义相似，反例与问题条款",
         "     用词雷同，会抬高规则触发权重"],
        size=9.5, color=INK, spacing=1.4)

    panel(s, rx, Inches(3.95), Inches(5.2), Inches(2.55), "red", "自证要求：先证后报")
    txt(s, rx + Inches(0.2), Inches(4.31), Inches(4.8), Inches(2.0),
        ["每条风险第一句必须是：",
         "「该条违反【Rxx】的判定条件「…」；",
         "  条款表现为「原文片段」」",
         "写不出原文片段 → 删除该条",
         "无法归类 → 允许 UNMATCHED，禁止套用相近规则"],
        size=9.5, color=INK, spacing=1.55)

    footer(s, "来源：agent/prompt.md（与 agent.json 的 prompt 字段逐字一致）")
    return s


# ---------------------------------------------------------------- 图 3 skills 并列


def fig3(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "四个自定义技能：一个技能压一项指标", "SKILLS",
         "skills/dist/*.zip ｜ 导入顺序：先装技能，再导入 agent.json")

    skills = [
        ("blue", "loan-rule-cards", "知识类 · 含 4 份 reference",
         ["按 rule_id 返回判定条件", "合规定式 / 缺陷形态", "已知误报清单"], "误报率"),
        ("green", "missing-clause-audit", "流程类 · 三态判定",
         ["缺失 / 效力不足 / 合规", "缺失型风险不放弃判定", "对照全文而非单条"], "检出率"),
        ("amber", "risk-selfcheck", "流程类 · 输出前四问",
         ["四问不过即删除该条", "抑制过度推断", "同一输入结果更稳定"], "一致性"),
        ("purple", "suggestion-compiler", "流程类 · 建议成文",
         ["必须是完整条款表述", "禁止「建议完善」类空话", "保留原条款结构与编号"], "建议可用性"),
    ]

    x0, y0 = Inches(0.6), Inches(1.62)
    cw, ch, gap = Inches(2.95), Inches(3.5), Inches(0.2)

    for i, (key, name, kind, items, metric) in enumerate(skills):
        x = x0 + (cw + gap) * i
        panel(s, x, y0, cw, ch, key)

        b = box(s, x + Inches(0.16), y0 + Inches(0.16), cw - Inches(0.32), Inches(0.46),
                PAL[key][1], None, radius=0.1)
        put(b, name, size=11, bold=True, color=WHITE)

        txt(s, x + Inches(0.18), y0 + Inches(0.72), cw - Inches(0.36), Inches(0.24),
            kind, size=8.5, color=SUB)

        yy = y0 + Inches(1.02)
        for it in items:
            c = box(s, x + Inches(0.16), yy, cw - Inches(0.32), Inches(0.52),
                    WHITE, PAL[key][1], radius=0.08)
            put(c, it, size=9.5, color=PAL[key][2], align=PP_ALIGN.LEFT)
            c.text_frame.margin_left = Inches(0.1)
            yy += Inches(0.6)

        tag = box(s, x + Inches(0.16), y0 + ch - Inches(0.55), cw - Inches(0.32),
                  Inches(0.36), WHITE, PAL[key][1], radius=0.14)
        put(tag, f"目标指标：{metric}", size=9, bold=True, color=PAL[key][2])

    bar = box(s, Inches(0.6), Inches(5.35), Inches(12.13), Inches(0.72),
              RGBColor(0xEA, 0xF1, 0xFE), PAL["blue"][1], radius=0.06)
    put(bar, ["四个技能各压一项指标：规则卡片压误报、缺失审计提检出、输出自检保一致、建议编译提可用性",
              "导入顺序：技能仓库上传 4 个 zip → 再导入 agent.json（否则平台报依赖缺失）"],
        size=9.5, color=NAVY, spacing=1.45)

    footer(s, "来源：skills/README.md ｜ agent.json 的 skill_names")
    return s


# ---------------------------------------------------------------- 图 4 测试流程


def fig4(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "测试流程：三步串联，顺序不可交换", "TEST PIPELINE",
         "28 份合同 ｜ 约 2900 条条款 ｜ 75 条计分标注")

    steps = [
        ("blue", "① 批量推理", "batch_run.py",
         ["输入：28 份合同条款", "输出：模型原始 JSON", "平均 35 秒/份，共约 17 分钟"]),
        ("red", "② 确定性闸门", "tools/gate.py",
         ["输入：原始 JSON + 条款", "两条定式：R16 否决 / R38 补报", "输出：校正后 JSON + 闸门日志"]),
        ("green", "③ 指标计算", "tools/evaluate.py",
         ["输入：标注 + 校正结果", "输出：五项指标 + 漏检/误报明细", "生成 docs/TEST_REPORT.md"]),
    ]

    y = Inches(1.62)
    hgt = Inches(1.28)
    for i, (key, title, cmd, items) in enumerate(steps):
        panel(s, Inches(0.6), y, Inches(9.1), hgt, key, title)
        txt(s, Inches(0.78), y + Inches(0.42), Inches(2.4), Inches(0.26),
            cmd, size=9.5, bold=True, color=PAL[key][1])
        for j, it in enumerate(items):
            txt(s, Inches(3.0), y + Inches(0.16) + Inches(0.3) * j, Inches(6.5), Inches(0.26),
                f"· {it}", size=9.5, color=INK)
        if i < 2:
            down_arrow(s, Inches(4.9), y + hgt + Inches(0.02), Inches(0.22), Inches(0.16),
                       key="gray")
        y += hgt + Inches(0.22)

    # 右侧：闸门三性质
    panel(s, Inches(9.95), Inches(1.62), Inches(2.8), Inches(4.5), "red",
          "闸门为什么是代码")
    txt(s, Inches(10.12), Inches(2.02), Inches(2.5), Inches(4.0),
        ["幂等",
         "二次运行 0 处改动",
         "",
         "可审计",
         "每处改动写 gate_log.json",
         "",
         "可回滚",
         "支持 --dry-run 只看不改",
         "",
         "确定性",
         "同输入必然同输出，",
         "不受模型波动影响"],
        size=9, color=INK, spacing=1.35)

    footer(s, "来源：tools/batch_run.py → tools/gate.py → tools/evaluate.py")
    return s


# ---------------------------------------------------------------- 图 5 指标结果


def fig5(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "指标结果：六项全部达标，且留有余量", "EVALUATION RESULT",
         "口径：20 条客观规则计分，20 条主观规则仅作提示")

    rows = [
        ("风险条款检出率", "100.0%", "≥ 85%", 100, "blue"),
        ("误报率", "2.6%", "≤ 15%", 17, "green"),
        ("原文定位准确率", "100.0%", "= 100%", 100, "blue"),
        ("风险等级一致率", "100.0%", "≥ 85%", 100, "blue"),
        ("修改建议可用性", "96.0%", "≥ 85%", 96, "blue"),
        ("三次一致性", "1.000", "≥ 0.90", 100, "green"),
    ]

    x_label = Inches(0.75)
    x_bar = Inches(3.55)
    bar_w = Inches(4.75)
    x_val = Inches(8.5)
    x_req = Inches(9.75)
    x_ok = Inches(10.95)
    y = Inches(1.65)
    row_h = Inches(0.66)

    # 表头
    txt(s, x_label, y - Inches(0.3), Inches(2.6), Inches(0.24), "指标", size=9, bold=True, color=SUB)
    txt(s, x_bar, y - Inches(0.3), Inches(2.0), Inches(0.24), "实测", size=9, bold=True, color=SUB)
    txt(s, x_req, y - Inches(0.3), Inches(1.1), Inches(0.24), "要求", size=9, bold=True, color=SUB)
    txt(s, x_ok, y - Inches(0.3), Inches(1.4), Inches(0.24), "判定", size=9, bold=True, color=SUB)

    for name, val, req, pct, key in rows:
        txt(s, x_label, y + Inches(0.14), Inches(2.6), Inches(0.3), name, size=11, color=INK)

        box(s, x_bar, y + Inches(0.2), bar_w, Inches(0.22),
            RGBColor(0xEE, 0xF1, 0xF5), None, radius=0.2, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
        fill_w = int(bar_w * pct / 100)
        if fill_w > 0:
            box(s, x_bar, y + Inches(0.2), fill_w, Inches(0.22),
                PAL[key][1], None, radius=0.2, shape=MSO_SHAPE.ROUNDED_RECTANGLE)

        txt(s, x_val, y + Inches(0.14), Inches(1.05), Inches(0.3), val,
            size=11.5, bold=True, color=PAL[key][1], align=PP_ALIGN.RIGHT)
        txt(s, x_req, y + Inches(0.15), Inches(1.05), Inches(0.3), req, size=10, color=SUB)

        ok = box(s, x_ok, y + Inches(0.14), Inches(0.86), Inches(0.3),
                 RGBColor(0xE4, 0xEC, 0xFB), PAL["green"][1], radius=0.18)
        put(ok, "达标", size=9, bold=True, color=PAL["green"][2])

        y += row_h

    # 底部口径条
    bar = box(s, Inches(0.6), Inches(6.05), Inches(12.13), Inches(0.72),
              RGBColor(0xEA, 0xF1, 0xFE), PAL["blue"][1], radius=0.06)
    put(bar, ["留有余量：检出率高于要求 15 个百分点；误报率低于上限 12.4 个百分点",
              "剩余 2 条误报均出现在 C02（该合同标注 0 条），成因已写入测试报告「已知局限」"],
        size=9.5, color=NAVY, spacing=1.45)

    footer(s, "来源：docs/TEST_REPORT.md")
    return s


# ---------------------------------------------------------------- 图 6 架构总结


def fig6(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, "架构总结：三层分工 + 六环节链路", "ARCHITECTURE",
         "位置由代码算 ｜ 判断由模型做 ｜ 依据必须可溯源")

    # 三层
    layers = [
        ("blue", "前端 web/", ["三栏联动", "上传 / 导出 / 打印", "按字符偏移高亮"], Inches(1.55)),
        ("green", "服务层 api/", ["解析 · 切分 · 闸门", "参数校验 · 落盘", "报告导出"], Inches(3.0)),
        ("purple", "智能体 Nexent", ["40 条规则知识库", "4 个自定义技能", "结构化 JSON 输出"], Inches(4.45)),
    ]
    for key, title, items, y in layers:
        panel(s, Inches(0.6), y, Inches(3.55), Inches(1.2), key, title)
        for j, it in enumerate(items):
            txt(s, Inches(0.78), y + Inches(0.42) + Inches(0.24) * j, Inches(3.2), Inches(0.22),
                f"· {it}", size=8.5, color=INK)

    for gy in (Inches(2.78), Inches(4.23)):
        down_arrow(s, Inches(2.2), gy, Inches(0.24), Inches(0.16), key="gray")

    # 数据层
    panel(s, Inches(0.6), Inches(5.75), Inches(3.55), Inches(0.85), "gray", "数据 data/")
    txt(s, Inches(0.78), Inches(6.12), Inches(3.2), Inches(0.3),
        "clauses / labels / rules / predictions", size=8, color=SUB)

    # 右侧：六环节链路
    panel(s, Inches(4.45), Inches(1.55), Inches(8.28), Inches(5.05), "blue",
          "一次审查的六个环节")
    steps = [("上传", "docx/pdf"), ("解析", "段落+表格"), ("切分", "第X条·偏移"),
             ("调智能体", "SSE 流"), ("过闸门", "确定性"), ("落盘展示", "JSON+高亮")]
    x = Inches(4.68)
    y = Inches(2.35)
    cw = Inches(1.2)
    gap = Inches(0.16)
    for i, (t, d) in enumerate(steps):
        c = box(s, x, y, cw, Inches(0.72), WHITE, PAL["blue"][1], radius=0.08)
        put(c, [t, d], size=9.5, bold=False, color=PAL["blue"][2], spacing=1.3)
        c.text_frame.paragraphs[0].runs[0].font.bold = True
        c.text_frame.paragraphs[1].runs[0].font.size = Pt(7.5)
        c.text_frame.paragraphs[1].runs[0].font.color.rgb = SUB
        if i < 5:
            arrow(s, x + cw + Inches(0.01), y + Inches(0.26), Inches(0.14), Inches(0.2),
                  key="blue")
        x += cw + gap

    # 关键约束三条
    txt(s, Inches(4.7), Inches(3.35), Inches(7.6), Inches(0.24), "三条职责边界", size=11, bold=True, color=NAVY)
    bounds = [
        ("位置由代码算", "切分与偏移不经模型，定位准确率因此可达 100%"),
        ("判断由模型做", "模型只回答是否违反规则，并给出理由与建议"),
        ("依据必须可溯源", "查不到条文则如实标注「未检索到权威依据」，不编造"),
    ]
    yy = Inches(3.72)
    for t, d in bounds:
        c = box(s, Inches(4.7), yy, Inches(7.75), Inches(0.68), WHITE, PAL["blue"][1], radius=0.06)
        txt(s, Inches(4.88), yy + Inches(0.09), Inches(2.3), Inches(0.26), t, size=10, bold=True, color=NAVY)
        txt(s, Inches(7.15), yy + Inches(0.1), Inches(5.1), Inches(0.46), d, size=9, color=SUB)
        yy += Inches(0.8)

    footer(s, "来源：docs/DESIGN.md ｜ api/server.py ｜ agent/prompt.md")
    return s


def main() -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    fig1(prs)
    fig2(prs)
    fig3(prs)
    fig4(prs)
    fig5(prs)
    fig6(prs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"已生成 {len(prs.slides)} 页 → {OUT}")


if __name__ == "__main__":
    main()
