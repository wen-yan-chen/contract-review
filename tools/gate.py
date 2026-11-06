"""确定性闸门：在模型输出落盘前做最后一次机械校正。

为什么需要它：技能（SKILL.md）能约束模型，但激活与执行由模型判断，
同一份合同两次运行可能一次报、一次不报。指标不能建在"模型这次听话"上。
闸门只做两类**定式可判**的校正，每条都能指出来源：

  A. 否决 R16：条款已写明「最高债权额为人民币 X 万元」且没有「为准 / 不持异议 /
     额度内 / 授信余额」等模糊限定 → 该条 R16 必然不成立。
     来源：data/review/fp_list.md 第 2/7/11/19/28 条复核结论（4 条误报同因）。

  B. 补报 R38：全文没有电子签名风险，但存在「电子签名……以出借人系统记录为准」
     的缺陷定式 → 补报。
     来源：data/review/fp_list.md 之外的三条漏检（C03-083 / C21-092 / C25-091），
     规则标题写作"缺失"，模型只判有无，效力不足的写法被放过。

幂等：对同一份结果重复执行，输出不变。

用法：
    from tools.gate import apply_gates
    pred, log = apply_gates(pred, clauses)

    python tools/gate.py --data-root data          # 就地校正已有结果
    python tools/gate.py --data-root data --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---- R16：合规定式 ----------------------------------------------------------
RE_R16_STATED = re.compile(r"最高债权额为人民币\s*[\d.]+\s*万元")
RE_R16_VAGUE = re.compile(r"为准|不持异议|额度内|授信余额|另行商定|待定")

# ---- R38：缺陷定式 ----------------------------------------------------------
RE_ESIGN_DEFECT = re.compile(r"电子签名[^。]{0,60}?(?:系统记录为准|不得以未收到)")

ESIGN_RISK_TYPE = "合规-电子签名效力"
ESIGN_SUGGESTION = (
    "建议改为：本合同采用可靠电子签名订立，与书面形式具有同等法律效力；"
    "出借人应向借款人提供可查阅、可下载的合同文本及签署时间戳记录。"
)


def _r16_is_compliant(clause_text: str) -> bool:
    return bool(RE_R16_STATED.search(clause_text)) and not RE_R16_VAGUE.search(clause_text)


def apply_gates(pred: dict, clauses: list[dict]) -> tuple[dict, list[dict]]:
    """对单份合同的审查结果执行闸门，返回 (新结果, 改动日志)。"""
    by_no = {c.get("clause_no"): c for c in clauses}
    log: list[dict] = []
    kept: list[dict] = []

    for risk in pred.get("risks") or []:
        clause_text = (by_no.get(risk.get("clause_no")) or {}).get("text", "")
        if risk.get("rule_id") == "R16" and _r16_is_compliant(clause_text):
            log.append({
                "action": "drop",
                "rule_id": "R16",
                "clause_no": risk.get("clause_no"),
                "risk_type": risk.get("risk_type"),
                "reason": "条款已写明具体最高债权额，属合规定式",
            })
            continue
        kept.append(risk)

    if not any(ESIGN_RISK_TYPE in (r.get("risk_type") or "") for r in kept):
        for clause in clauses:
            text = clause.get("text", "")
            hit = RE_ESIGN_DEFECT.search(text)
            if not hit:
                continue
            kept.append({
                "clause_no": clause["clause_no"],
                "risk_type": ESIGN_RISK_TYPE,
                "rule_id": "R38",
                "risk_level": "低",
                "quote": hit.group(0),
                "problem": (
                    "该条违反【R38】的判定条件「电子签名效力是否达到可靠电子签名标准」；"
                    "条款表现为「电子签名的效力以出借人系统记录为准」，"
                    "以出借人单方系统记录替代可靠电子签名要件，签署效力存在争议。"
                ),
                "suggestion": ESIGN_SUGGESTION,
                "legal_basis": "未检索到权威依据",
            })
            log.append({
                "action": "add",
                "rule_id": "R38",
                "clause_no": clause["clause_no"],
                "risk_type": ESIGN_RISK_TYPE,
                "reason": "命中电子签名效力缺陷定式",
            })
            break

    pred = dict(pred)
    pred["risks"] = kept
    return pred, log


# ---------------------------------------------------------------- CLI


def gate_file(pred_path: Path, clauses_path: Path, dry_run: bool = False) -> list[dict]:
    pred = json.loads(pred_path.read_text(encoding="utf-8"))
    clauses = json.loads(clauses_path.read_text(encoding="utf-8"))
    if isinstance(clauses, dict):
        clauses = clauses.get("clauses", [])

    before = len(pred.get("risks") or [])
    pred, log = apply_gates(pred, clauses)
    if not log:
        return []

    if not dry_run:
        pred_path.write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")

    for item in log:
        item["cid"] = pred_path.stem
        item["before"] = before
        item["after"] = len(pred.get("risks") or [])
    return log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default="data")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.data_root)
    entries: list[dict] = []
    for pred_path in sorted((root / "predictions").glob("C*.json")):
        clauses_path = root / "clauses" / pred_path.name
        if not clauses_path.exists():
            continue
        entries.extend(gate_file(pred_path, clauses_path, args.dry_run))

    for e in entries:
        print(f"  {e['cid']} {e['action']:4s} {e['clause_no']} {e['risk_type']}（{e['reason']}）")
    print(f"\n共 {len(entries)} 处校正" + ("（dry-run，未写盘）" if args.dry_run else ""))

    if entries and not args.dry_run:
        log_path = root / "review" / "gate_log.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"日志已写入 {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
