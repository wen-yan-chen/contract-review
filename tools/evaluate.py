r"""评测跑分器 —— 把"检出率/误报率/定位准确率"算成可复算的数字。

输入：
  data/clauses/{cid}.json      条款表（clause_id / clause_no / text）
  data/labels/{cid}.json       人工标注（ground truth）
  data/predictions/{cid}.json  系统输出（模型原始返回的 JSON）
  data/rules/rules.yaml        规则库（judge 字段决定是否计入指标）
  data/labels/type_map.yaml    风险类型归一化映射（可选）

计分范围：
  只有 judge=deterministic 的规则参与检出率/误报率计算；
  judge=discretionary 的规则视为"提示性建议"，输出但不计入指标。

用法：
  python evaluate.py --data-root D:\\contest-32\\data
  python evaluate.py --data-root ... --out D:\\contest-32\\docs\\TEST_REPORT.md
  python evaluate.py --runs run1,run2,run3
  python evaluate.py --min-confidence 0.8
  python evaluate.py --demo
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import tempfile
from pathlib import Path

# 验收阈值（官方课题文档）
THRESHOLDS = {
    "detection_rate": 0.85,
    "false_positive_rate": 0.15,
    "locate_accuracy": 1.00,
    "level_accuracy": 0.85,
    "suggestion_usable": 0.85,
}
LOCATE_SIM = 0.90


# ----------------------------------------------------------------- 工具


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def load_yaml(p: Path):
    if not p.exists():
        return None
    try:
        import yaml  # type: ignore
    except ImportError:
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def norm_type(t: str, type_map: dict | None) -> str:
    if not type_map:
        return (t or "").strip()
    for canonical, aliases in type_map.items():
        if t == canonical or t in (aliases or []):
            return canonical
    return (t or "").strip()


def clause_no_to_id(clauses: list[dict]) -> dict[str, str]:
    return {c["clause_no"]: c["clause_id"] for c in clauses if c.get("clause_no")}


# ----------------------------------------------------------------- 匹配


def match_one(label: dict, pred: dict, clauses: list[dict],
              type_map: dict | None, rules: dict, min_conf: float = 0.0,
              scoring: set | None = None, levels: set | None = None) -> dict:
    """计算单份合同的 TP/FP/FN 与各项指标。

    min_conf > 0  按置信度过滤预测
    scoring       只统计 rule_id 在此集合内的风险（None = 全部）
    levels        只统计 risk_level 在此集合内的风险（None = 全部）
    """
    no2id = clause_no_to_id(clauses)
    clause_text = {c["clause_id"]: c.get("text", "") for c in clauses}

    def key_of(item: dict, is_pred: bool):
        cid = item.get("clause_id") or (no2id.get(item.get("clause_no", "")) if is_pred else None)
        return (cid, norm_type(item.get("risk_type", ""), type_map))

    lab_items = label.get("risks") or []
    prd_items = pred.get("risks") or []
    if scoring:
        lab_items = [r for r in lab_items if r.get("rule_id") in scoring]
        prd_items = [r for r in prd_items if r.get("rule_id") in scoring]
    if levels:
        lab_items = [r for r in lab_items if r.get("risk_level") in levels]
        prd_items = [r for r in prd_items if r.get("risk_level") in levels]
    if min_conf > 0:
        prd_items = [r for r in prd_items if float(r.get("confidence") or 0) >= min_conf]

    labels = {key_of(r, False): r for r in lab_items}
    preds = {key_of(r, True): r for r in prd_items}

    tp_keys = labels.keys() & preds.keys()
    fp_keys = preds.keys() - labels.keys()
    fn_keys = labels.keys() - preds.keys()

    located = 0
    level_ok = 0
    usable = 0
    for k in tp_keys:
        lab, pr = labels[k], preds[k]

        q = (pr.get("quote") or "").strip()
        text = clause_text.get(k[0], "")
        exact = bool(q) and q in text
        sim = difflib.SequenceMatcher(None, q, (lab.get("quote") or "").strip()).ratio()
        if exact and sim >= LOCATE_SIM:
            located += 1

        if pr.get("risk_level") == lab.get("risk_level"):
            level_ok += 1

        sug = (pr.get("suggestion") or "").strip()
        kws = (rules.get(pr.get("rule_id")) or {}).get("suggestion_keywords") or []
        if kws:
            if any(str(kw) in sug for kw in kws):
                usable += 1
        elif len(sug) >= 10 and sug != (lab.get("suggestion") or "").strip():
            usable += 1

    tp, fp, fn = len(tp_keys), len(fp_keys), len(fn_keys)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "labels": len(labels), "preds": len(preds),
        "detection_rate": (tp / (tp + fn)) if (tp + fn) else 1.0,
        "false_positive_rate": (fp / (fp + tp)) if (fp + tp) else 0.0,
        "locate_accuracy": (located / tp) if tp else 1.0,
        "level_accuracy": (level_ok / tp) if tp else 1.0,
        "suggestion_usable": (usable / tp) if tp else 1.0,
        "missed": [(k[0], k[1]) for k in sorted(fn_keys)],
        "spurious": [(k[0], k[1]) for k in sorted(fp_keys)],
    }


def aggregate(rows: list[dict]) -> dict:
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "detection_rate": tp / (tp + fn) if (tp + fn) else 1.0,
        "false_positive_rate": fp / (tp + fp) if (tp + fp) else 0.0,
        "locate_accuracy": sum(r["locate_accuracy"] * r["tp"] for r in rows) / tp if tp else 1.0,
        "level_accuracy": sum(r["level_accuracy"] * r["tp"] for r in rows) / tp if tp else 1.0,
        "suggestion_usable": sum(r["suggestion_usable"] * r["tp"] for r in rows) / tp if tp else 1.0,
    }


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a | b) else 1.0


# ----------------------------------------------------------------- 报告


def render_markdown(rows: list[tuple[str, dict]], agg: dict,
                    consistency: dict | None, scoring_note: str) -> str:
    lines = ["# 验收指标自测报告", "",
             "> 由 `tools/evaluate.py` 自动生成。匹配键 = (clause_id, risk_type)。",
             f"> 计分范围：{scoring_note}", "",
             "## 分合同明细", "",
             "| 合同 | 标注数 | 检出 | 漏检 | 误报 | 检出率 | 误报率 | 定位准确率 | 等级一致率 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for cid, r in rows:
        lines.append(
            f"| {cid} | {r['labels']} | {r['tp']} | {r['fn']} | {r['fp']} | "
            f"{r['detection_rate']:.1%} | {r['false_positive_rate']:.1%} | "
            f"{r['locate_accuracy']:.1%} | {r['level_accuracy']:.1%} |")

    lines += ["", "## 总体指标", "", "| 指标 | 实测 | 阈值 | 结论 |", "|---|---:|---:|---|"]

    def v(val, th, lower=False):
        ok = val <= th if lower else val >= th
        return "达标" if ok else "未达标"

    lines.append(f"| 风险条款检出率 | {agg['detection_rate']:.1%} | >=85% | "
                 f"{v(agg['detection_rate'], THRESHOLDS['detection_rate'])} |")
    lines.append(f"| 误报率 | {agg['false_positive_rate']:.1%} | <=15% | "
                 f"{v(agg['false_positive_rate'], THRESHOLDS['false_positive_rate'], True)} |")
    lines.append(f"| 原文定位准确率 | {agg['locate_accuracy']:.1%} | =100% | "
                 f"{v(agg['locate_accuracy'], THRESHOLDS['locate_accuracy'])} |")
    lines.append(f"| 风险等级一致率 | {agg['level_accuracy']:.1%} | >=85% | "
                 f"{v(agg['level_accuracy'], THRESHOLDS['level_accuracy'])} |")
    lines.append(f"| 修改建议可用性 | {agg['suggestion_usable']:.1%} | >=85% | "
                 f"{v(agg['suggestion_usable'], THRESHOLDS['suggestion_usable'])} |")
    lines.append(f"\n样本量：TP={agg['tp']}，FP={agg['fp']}，FN={agg['fn']}（共 {agg['tp'] + agg['fn']} 条计分标注）")

    if consistency:
        lines += ["", "## 3 次一致性", "", "| 合同 | 两两 Jaccard 最小值 | 结论 |", "|---|---:|---|"]
        for cid, j in consistency.items():
            lines.append(f"| {cid} | {j:.3f} | {'通过' if j >= 0.90 else '未通过'} |")

    lines += ["", "## 漏检与误报明细", ""]
    for cid, r in rows:
        if r["missed"]:
            lines.append(f"- **{cid} 漏检**：{r['missed']}")
        if r["spurious"]:
            lines.append(f"- **{cid} 误报**：{r['spurious']}")
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------- 主流程


def run(data_root: Path, out_path: Path | None, runs: list[str] | None,
        min_conf: float = 0.0, levels: set | None = None,
        all_rules: bool = False) -> int:
    clauses_dir = data_root / "clauses"
    labels_dir = data_root / "labels"
    pred_dir = data_root / "predictions"

    type_map_raw = load_yaml(labels_dir / "type_map.yaml") or {}
    rules_raw = load_yaml(data_root / "rules" / "rules.yaml") or []
    if isinstance(rules_raw, dict):
        rules_raw = rules_raw.get("rules", [])
    rules = {r["rule_id"]: r for r in rules_raw if isinstance(r, dict) and r.get("rule_id")}

    scoring = {rid for rid, r in rules.items() if r.get("judge") == "deterministic"}
    if all_rules:
        note = f"全部 {len(rules)} 条规则（--all-rules）"
        scoring_set = None
    elif scoring:
        note = (f"{len(scoring)}/{len(rules)} 条规则（judge=deterministic）；"
                f"其余 {len(rules) - len(scoring)} 条为提示性建议，不计入指标")
        scoring_set = scoring
    else:
        note = f"全部 {len(rules)} 条规则（规则库未标注 judge）"
        scoring_set = None
    print(f"计分范围: {note}\n")

    labels = sorted(p for p in labels_dir.glob("*.json")
                    if p.stem.lower() not in ("schema", "split", "type_map", "manifest"))
    if not labels:
        print(f"未找到标注: {labels_dir}")
        return 1

    rows: list[tuple[str, dict]] = []
    for lp in labels:
        cid = lp.stem
        cp, pp = clauses_dir / f"{cid}.json", pred_dir / f"{cid}.json"
        if not cp.exists() or not pp.exists():
            print(f"跳过 {cid}（缺 {'条款表' if not cp.exists() else '预测结果'}）")
            continue
        clauses = load_json(cp)
        if isinstance(clauses, dict):
            clauses = clauses.get("clauses", [])
        rows.append((cid, match_one(load_json(lp), load_json(pp), clauses,
                                     type_map_raw, rules, min_conf, scoring_set, levels)))

    if not rows:
        print("没有可评测的数据（检查 clauses/ 与 predictions/）")
        return 1

    agg = aggregate([r for _, r in rows])

    consistency = None
    if runs:
        consistency = {}
        for cid, _ in rows:
            sets = []
            clauses = load_json(clauses_dir / f"{cid}.json")
            if isinstance(clauses, dict):
                clauses = clauses.get("clauses", [])
            cid_map = clause_no_to_id(clauses)
            for rname in runs:
                fp = pred_dir / rname / f"{cid}.json"
                if not fp.exists():
                    break
                pred = load_json(fp)
                sets.append({(p.get("clause_id") or cid_map.get(p.get("clause_no", "")),
                              norm_type(p.get("risk_type", ""), type_map_raw))
                             for p in (pred.get("risks") or [])})
            if len(sets) >= 2:
                consistency[cid] = min(jaccard(sets[i], sets[j])
                                       for i in range(len(sets)) for j in range(i + 1, len(sets)))

    md = render_markdown(rows, agg, consistency, note)
    print(md)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
        print(f"\n报告已写入: {out_path}")

    passed = (agg["detection_rate"] >= THRESHOLDS["detection_rate"]
              and agg["false_positive_rate"] <= THRESHOLDS["false_positive_rate"]
              and agg["locate_accuracy"] >= THRESHOLDS["locate_accuracy"]
              and agg["level_accuracy"] >= THRESHOLDS["level_accuracy"]
              and agg["suggestion_usable"] >= THRESHOLDS["suggestion_usable"])
    print("总体结论:", "全部达标" if passed else "存在未达标项")
    return 0 if passed else 2


def demo() -> int:
    """自检：1 条命中 + 1 条漏检 + 1 条误报。"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for d in ("clauses", "labels", "predictions", "rules"):
            (root / d).mkdir()

        t1 = "逾期罚息按合同利率的三倍计收，且不受任何上限约束。"
        t2 = "保证人自愿为该笔借款提供保证。"
        (root / "clauses" / "C99.json").write_text(json.dumps([
            {"clause_id": "C99-001", "clause_no": "第十二条", "text": t1},
            {"clause_id": "C99-002", "clause_no": "第二十条", "text": t2},
        ], ensure_ascii=False), encoding="utf-8")

        q1 = "逾期罚息按合同利率的三倍计收"
        s = t1.index(q1)
        (root / "labels" / "C99.json").write_text(json.dumps({"contract_id": "C99", "risks": [
            {"risk_id": "C99-R1", "clause_id": "C99-001", "clause_no": "第十二条",
             "risk_type": "利率-罚息超限", "rule_id": "R02", "risk_level": "高",
             "char_start": s, "char_end": s + len(q1), "quote": q1,
             "problem": "p", "suggestion": "改为上浮50%", "legal_basis": {"verify_status": "pending"}},
            {"risk_id": "C99-R2", "clause_id": "C99-002", "clause_no": "第二十条",
             "risk_type": "担保-保证方式不明", "rule_id": "R11", "risk_level": "中",
             "char_start": 0, "char_end": 5, "quote": "保证人自愿",
             "problem": "p", "suggestion": "改为连带责任保证", "legal_basis": {"verify_status": "pending"}},
        ], "consistency_checks": []}, ensure_ascii=False), encoding="utf-8")

        (root / "predictions" / "C99.json").write_text(json.dumps({"risks": [
            {"clause_no": "第十二条", "risk_type": "利率-罚息超限", "rule_id": "R02",
             "risk_level": "高", "quote": q1, "problem": "p",
             "suggestion": "按合同利率上浮50%计收罚息", "legal_basis": "待核验"},
            {"clause_no": "第二十条", "risk_type": "担保-抵押未登记", "rule_id": "R14",
             "risk_level": "高", "quote": "提供保证", "problem": "p",
             "suggestion": "应办理抵押登记", "legal_basis": "待核验"},
        ], "consistency_checks": []}, ensure_ascii=False), encoding="utf-8")

        print("--- DEMO：预期 TP=1, FN=1, FP=1 ---")
        code = run(root, None, None)
        ok = code == 2
        print("\nDEMO 结论:", "跑分器工作正常" if ok else "结果异常")
        return 0 if ok else 1


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="验收指标跑分器")
    ap.add_argument("--data-root", default="data")
    ap.add_argument("--out", default=None, help="报告写入路径")
    ap.add_argument("--runs", default=None, help="多次运行目录名，逗号分隔")
    ap.add_argument("--min-confidence", type=float, default=0.0,
                    help="只统计 confidence >= 该值的预测")
    ap.add_argument("--levels", default=None,
                    help="只统计指定风险等级，逗号分隔，如 高 或 高,中")
    ap.add_argument("--all-rules", action="store_true",
                    help="忽略 judge 分类，40 条规则全部计分")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.demo:
        return demo()
    runs = [x.strip() for x in args.runs.split(",")] if args.runs else None
    levels = {x.strip() for x in args.levels.split(",")} if args.levels else None
    return run(Path(args.data_root), Path(args.out) if args.out else None, runs,
               args.min_confidence, levels, args.all_rules)


if __name__ == "__main__":
    raise SystemExit(main())
