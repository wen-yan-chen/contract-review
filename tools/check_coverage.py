r"""合同覆盖率检查：40 条规则在每份合同里是否有对应条款（合规 or 问题）。

为什么需要它：
  pilot 发现模型大量报"未约定 X"，排查后确认合同里确实没有该条款。
  这说明数据构造不完整——非植入条款没有落在合同里，导致模型的正确判断被算成误报。

判定标准（每份合同 × 每条规则）：
  ok    该合同包含此规则的合规范式
  bad   该合同包含此规则的问题表述（= 植入）
  none  ⚠ 两者都没有 → 该规则在此合同"无对应条款"，会产生误报

用法：
  python check_coverage.py            # 检查 data/ 下全部合同
  python check_coverage.py --ids C01,C13
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

DATA = Path(r"D:\contest-32\data")
GEN = r"D:\contest-32\tools\gen_dataset.py"


def _present(text: str, body: str) -> bool:
    """支持 {amount} 这类占位符：占位符位置匹配任意非空内容。"""
    if not text:
        return False
    if "{" not in text:
        return text in body
    # 先切分再逐段转义，避免把占位符的花括号也转义掉
    parts = re.split(r"(\{[^}]+\})", text)
    pattern = "".join(".+?" if (p.startswith("{") and p.endswith("}")) else re.escape(p)
                      for p in parts if p)
    return re.search(pattern, body, re.S) is not None


def load_rule_texts() -> dict[str, dict]:
    spec = importlib.util.spec_from_file_location("gen_dataset_mod", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {r["rule_id"]: {"ok": (r.get("ok") or "").strip(),
                           "bad": (r.get("bad") or "").strip()} for r in mod.RULES}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=None)
    args = ap.parse_args()

    texts = load_rule_texts()
    split = json.loads((DATA / "labels" / "split.json").read_text(encoding="utf-8"))
    ids = ([x.strip() for x in args.ids.split(",")] if args.ids
           else sorted(split["dev"] + split["holdout"]))

    total_none = 0
    print(f"{'合同':6}{'ok':>5}{'bad':>5}{'none':>6}   缺失规则的合同检查")
    print("-" * 60)
    for cid in ids:
        cp = DATA / "clauses" / f"{cid}.json"
        if not cp.exists():
            print(f"{cid:6} 缺条款表")
            continue
        clauses = json.loads(cp.read_text(encoding="utf-8"))
        if isinstance(clauses, dict):
            clauses = clauses["clauses"]
        body = "\n".join(c["text"] for c in clauses)

        n_ok = n_bad = 0
        missing = []
        for rid, t in texts.items():
            has_bad = _present(t["bad"], body)
            has_ok = _present(t["ok"], body)
            if has_bad:
                n_bad += 1
            elif has_ok:
                n_ok += 1
            else:
                missing.append(rid)
        total_none += len(missing)
        print(f"{cid:6}{n_ok:>5}{n_bad:>5}{len(missing):>6}   {','.join(missing[:8])}{'...' if len(missing) > 8 else ''}")

    print("-" * 60)
    print(f"合计「无对应条款」{total_none} 处（理想值应为 0）")
    print("结论:", "覆盖完整" if total_none == 0 else "覆盖不完整，会产生系统性误报")
    return 0 if total_none == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
