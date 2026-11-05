"""把 rules.yaml 导出为知识库可检索的 markdown。

用法：
  python export_kb.py --rules D:\\contest-32\\data\\rules\\rules.yaml --out D:\\contest-32\\data\\kb\\rules-full.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

HEADER = """# 贷款合同审查规则库（全量版 v1.0）

> 由 `tools/export_kb.py` 从 `data/rules/rules.yaml` 自动导出，**请勿手工编辑本文件**。
> 每条规则包含：规则编号、风险类型、风险等级、判定条件、常见表述、建议表述、依据。
> 依据字段为「待核验」时，输出必须写「未检索到权威依据」，不得编造法规名称与条号文号。
"""


def render_rule(r: dict, compliant: dict | None = None) -> str:
    lines = [f"## {r['rule_id']} {r.get('title', '')}", ""]
    lines.append(f"- 规则编号：{r['rule_id']}")
    lines.append(f"- 风险类型：{r.get('risk_type') or r.get('title', '')}")
    lines.append(f"- 所属分类：{r.get('category', '')}")
    lines.append(f"- 风险等级：{r.get('risk_level', '')}")

    detect = r.get("detect") or {}
    cond = detect.get("llm_hint") or detect.get("condition") or ""
    kws = detect.get("keywords") or []
    regex = detect.get("regex") or ""
    if cond:
        lines.append(f"- 判定条件：{cond}")
    if kws:
        lines.append(f"- 关键词：{'、'.join(str(k) for k in kws)}")
    if regex:
        lines.append(f"- 匹配模式：{regex}")

    if r.get("common_expression"):
        lines.append(f"- 常见表述：{r['common_expression']}")

    ok = (compliant or {}).get(r["rule_id"])
    if ok:
        lines.append(f"- 合规范式（**命中此表述时不得报告为风险**）：{ok}")

    if r.get("suggestion_template"):
        lines.append(f"- 建议表述：{r['suggestion_template']}")

    basis = r.get("legal_basis") or {}
    if isinstance(basis, dict):
        status = basis.get("verify_status", "pending")
        name = basis.get("name") or "待核验"
        article = basis.get("article") or ""
        if status == "verified":
            lines.append(f"- 依据：{name} {article}".strip())
        else:
            lines.append("- 依据：待核验")
    else:
        lines.append(f"- 依据：{basis}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default=r"D:\contest-32\data\rules\rules.yaml")
    ap.add_argument("--compliant", default=r"D:\contest-32\data\rules\compliant.yaml")
    ap.add_argument("--out", default=r"D:\contest-32\data\kb\rules-full.md")
    args = ap.parse_args()

    data = yaml.safe_load(Path(args.rules).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("rules", [])
    if not data:
        print("规则库为空")
        return 1

    # 合规范式（反例清单）：来自 gen_dataset.py 的 ok 文本，用于压低误报
    compliant: dict[str, str] = {}
    cp = Path(args.compliant)
    if cp.exists():
        craw = yaml.safe_load(cp.read_text(encoding="utf-8"))
        if isinstance(craw, dict):
            craw = craw.get("rules", [])
        compliant = {x["rule_id"]: x.get("compliant_text", "") for x in craw or []}
        print(f"合规范式: {len(compliant)} 条")
    else:
        print(f"⚠️ 未找到合规范式文件 {cp}，导出结果将缺少反例（误报率可能偏高）")

    parts = [HEADER]
    by_cat: dict[str, list[dict]] = {}
    for r in data:
        by_cat.setdefault(r.get("category", "未分类"), []).append(r)

    parts.append("## 规则总览\n")
    parts.append("| 编号 | 风险类型 | 分类 | 等级 |\n|---|---|---|---|")
    for r in data:
        parts.append(f"| {r['rule_id']} | {r.get('risk_type') or r.get('title','')} | "
                     f"{r.get('category','')} | {r.get('risk_level','')} |")
    parts.append("")

    for cat, rs in by_cat.items():
        parts.append(f"# {cat}类规则（{len(rs)} 条）\n")
        for r in rs:
            parts.append(render_rule(r, compliant))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")

    pending = sum(1 for r in data if (r.get("legal_basis") or {}).get("verify_status") != "verified"
                  if isinstance(r.get("legal_basis"), dict))
    print(f"已导出 {len(data)} 条规则 → {out}")
    print(f"分类: { {k: len(v) for k, v in by_cat.items()} }")
    print(f"依据待核验: {pending} 条（需人工核对后改 verified）")
    print(f"文件大小: {out.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
