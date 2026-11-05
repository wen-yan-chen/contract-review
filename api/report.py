"""审查报告导出：markdown 与 docx 两种格式。"""

from __future__ import annotations

import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

DISCLAIMER = (
    "本报告由系统自动生成，仅作为合同审查的辅助参考，不构成法律意见；"
    "最终以法务与审批人员的书面意见为准。"
)


def _rows(pred: dict) -> list[dict]:
    return (pred or {}).get("risks") or []


def build_markdown(cid: str, name: str, clauses: list[dict], pred: dict) -> str:
    risks = _rows(pred)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [f"# 贷款合同审查报告", "",
             f"- 合同：{name}",
             f"- 编号：{cid}",
             f"- 条款数：{len(clauses)}",
             f"- 风险提示：{len(risks)} 处",
             f"- 生成时间：{now}", "",
             "---", ""]

    if not risks:
        lines += ["未发现需要提示的条款。", ""]

    for i, r in enumerate(risks, 1):
        basis = r.get("legal_basis")
        if isinstance(basis, dict):
            basis = basis.get("name") or "未检索到权威依据"
        lines += [
            f"## {i}. [{r.get('risk_level', '')}] {r.get('risk_type', '')}",
            "",
            f"- 条款：{r.get('clause_no', '')}",
            f"- 规则：{r.get('rule_id', '')}",
            f"- 原文：{r.get('quote', '')}",
            "",
            f"**问题**：{r.get('problem', '')}",
            "",
            f"**建议**：{r.get('suggestion', '')}",
            "",
            f"**依据**：{basis}",
            "",
            "---",
            "",
        ]

    checks = (pred or {}).get("consistency_checks") or []
    if checks:
        lines += ["## 授信批复比对", "", "| 要素 | 合同 | 授信批复 | 说明 |", "|---|---|---|---|"]
        for c in checks:
            lines.append(f"| {c.get('field', '')} | {c.get('contract_value', '')} | "
                         f"{c.get('credit_report_value', '')} | {c.get('note', '')} |")
        lines.append("")

    lines += ["---", "", f"> {DISCLAIMER}", ""]
    return "\n".join(lines)


def build_docx(cid: str, name: str, clauses: list[dict], pred: dict) -> bytes:
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(10.5)
    style.paragraph_format.line_spacing = 1.5

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("贷款合同审查报告")
    run.bold = True
    run.font.size = Pt(16)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(
        f"{name}　|　{cid}　|　{len(clauses)} 条条款　|　"
        f"{len(_rows(pred))} 处提示　|　{datetime.now():%Y-%m-%d %H:%M}"
    ).font.size = Pt(9)

    risks = _rows(pred)
    if not risks:
        doc.add_paragraph("未发现需要提示的条款。")

    for i, r in enumerate(risks, 1):
        h = doc.add_paragraph()
        hr = h.add_run(f"{i}. [{r.get('risk_level', '')}] {r.get('risk_type', '')}")
        hr.bold = True
        hr.font.size = Pt(11)

        doc.add_paragraph(f"条款：{r.get('clause_no', '')}　规则：{r.get('rule_id', '')}")
        q = doc.add_paragraph()
        q.paragraph_format.left_indent = Pt(12)
        q.add_run(f"原文：{r.get('quote', '')}").italic = True

        doc.add_paragraph(f"问题：{r.get('problem', '')}")
        doc.add_paragraph(f"建议：{r.get('suggestion', '')}")

        basis = r.get("legal_basis")
        if isinstance(basis, dict):
            basis = basis.get("name") or "未检索到权威依据"
        doc.add_paragraph(f"依据：{basis}")

    checks = (pred or {}).get("consistency_checks") or []
    if checks:
        doc.add_paragraph()
        h = doc.add_paragraph()
        h.add_run("授信批复比对").bold = True
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for cell, text in zip(table.rows[0].cells, ["要素", "合同", "授信批复", "说明"]):
            cell.text = text
        for c in checks:
            cells = table.add_row().cells
            for cell, text in zip(cells, [c.get("field", ""), c.get("contract_value", ""),
                                          c.get("credit_report_value", ""), c.get("note", "")]):
                cell.text = str(text or "")

    doc.add_paragraph()
    note = doc.add_paragraph()
    note.add_run(DISCLAIMER).font.size = Pt(9)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
