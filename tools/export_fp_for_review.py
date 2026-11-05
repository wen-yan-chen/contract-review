"""导出误报清单，供人工/辅助判定"是否成立"。

输出：
  data/review/fp_list.md   可读表格（条款原文 + 模型理由 + 规则判定条件）
  data/review/fp_list.json 结构化清单（供回填结论）
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

DATA = Path(r"D:\contest-32\data")
OUT = DATA / "review"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    rules = yaml.safe_load((DATA / "rules" / "rules.yaml").read_text(encoding="utf-8"))
    rules = rules["rules"] if isinstance(rules, dict) else rules
    det = {r["rule_id"] for r in rules if r.get("judge") == "deterministic"}
    rule_by_id = {r["rule_id"]: r for r in rules}

    split = json.loads((DATA / "labels" / "split.json").read_text(encoding="utf-8"))
    ids = sorted(split["dev"] + split["holdout"])

    items = []
    for cid in ids:
        lp, pp, cp = (DATA / "labels" / f"{cid}.json",
                      DATA / "predictions" / f"{cid}.json",
                      DATA / "clauses" / f"{cid}.json")
        if not (lp.exists() and pp.exists() and cp.exists()):
            continue
        clauses = json.loads(cp.read_text(encoding="utf-8"))
        if isinstance(clauses, dict):
            clauses = clauses["clauses"]
        no2id = {c["clause_no"]: c["clause_id"] for c in clauses if c.get("clause_no")}
        text_of = {c["clause_no"]: c.get("text", "") for c in clauses}

        lab = json.loads(lp.read_text(encoding="utf-8"))
        pred = json.loads(pp.read_text(encoding="utf-8"))

        L = {(r.get("clause_id"), r.get("risk_type")) for r in (lab.get("risks") or [])
             if r.get("rule_id") in det}
        for r in (pred.get("risks") or []):
            if r.get("rule_id") not in det:
                continue
            key = (no2id.get(r.get("clause_no")), r.get("risk_type"))
            if key in L:
                continue
            rule = rule_by_id.get(r.get("rule_id")) or {}
            items.append({
                "fp_id": f"{cid}-{r.get('rule_id')}-{r.get('clause_no')}",
                "cid": cid,
                "clause_no": r.get("clause_no"),
                "rule_id": r.get("rule_id"),
                "rule_title": rule.get("title", ""),
                "rule_condition": (rule.get("detect") or {}).get("llm_hint", ""),
                "risk_level": r.get("risk_level"),
                "clause_text": text_of.get(r.get("clause_no"), "")[:400],
                "quote": r.get("quote", ""),
                "problem": r.get("problem", ""),
                "verdict": "",          # 待填：成立 / 不成立 / 边界
                "reason": "",           # 待填：判定依据
            })

    (OUT / "fp_list.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 误报复核清单", "",
             f"共 {len(items)} 条。对每条判断：该风险在合同条款中**是否成立**。",
             "", "判定依据是「规则判定条件」，不是主观法律意见。", "",
             "| # | 合同 | 条款 | 规则 | 模型理由 | 条款原文 | 结论 |",
             "|---:|---|---|---|---|---|---|"]
    for i, it in enumerate(items, 1):
        lines.append(
            f"| {i} | {it['cid']} | {it['clause_no']} | {it['rule_id']} {it['rule_title']} | "
            f"{(it['problem'] or '')[:70]} | {(it['clause_text'] or '')[:70]} | |")

    (OUT / "fp_list.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"已导出 {len(items)} 条误报 → {OUT / 'fp_list.md'}")
    by_rule: dict[str, int] = {}
    for it in items:
        by_rule[it["rule_id"]] = by_rule.get(it["rule_id"], 0) + 1
    print("按规则分布:", dict(sorted(by_rule.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
