"""从 gen_dataset.py 的规则定义中抽取「合规表述」，生成反例清单。

动机：pilot 发现模型把合规写法（罚息上浮 50% 且设上限）误报为风险。
根因是知识库只告诉模型"什么算问题"，没告诉它"什么不算问题"。
本脚本把生成器里每条规则的 ok 文本抽出来，供 export_kb.py 写入知识库。
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import yaml

GEN = r"D:\contest-32\tools\gen_dataset.py"


def load_rules_module() -> list[dict]:
    spec = importlib.util.spec_from_file_location("gen_dataset_mod", GEN)
    mod = importlib.util.module_from_spec(spec)
    # 只加载常量，不触发 main（gen_dataset 应有 __main__ 保护）
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return getattr(mod, "RULES")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"D:\contest-32\data\rules\compliant.yaml")
    args = ap.parse_args()

    rules = load_rules_module()
    print(f"从 gen_dataset.py 读到 {len(rules)} 条规则")

    out: list[dict] = []
    missing = []
    for r in rules:
        ok = (r.get("ok") or "").strip()
        if not ok:
            missing.append(r.get("rule_id"))
            continue
        out.append({
            "rule_id": r["rule_id"],
            "risk_type": r.get("risk_type", ""),
            "category": r.get("category", ""),
            "compliant_text": ok,
            "note": "该表述为合规范式；命中此表述时不得报告为风险",
        })

    Path(args.out).write_text(
        yaml.safe_dump({"version": 1, "rules": out}, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8")
    print(f"已写出 {len(out)} 条合规范式 → {args.out}")
    if missing:
        print(f"⚠️ 缺少 ok 文本的规则: {missing}")

    # 顺带检查：与 rules.yaml 的 rule_id 是否一一对应
    rp = Path(r"D:\contest-32\data\rules\rules.yaml")
    raw = yaml.safe_load(rp.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("rules", [])
    ids = {r["rule_id"] for r in raw}
    ours = {o["rule_id"] for o in out}
    print(f"rules.yaml {len(ids)} 条；合规范式 {len(ours)} 条")
    print(f"  仅 rules.yaml 有: {sorted(ids - ours) or '无'}")
    print(f"  仅合规范式有: {sorted(ours - ids) or '无'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
